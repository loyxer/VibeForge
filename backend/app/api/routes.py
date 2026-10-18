import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from app import auth, photos, projects, publishing, supabase, usage, user_photos, versions
from app.auth import current_user
from app.generation.base import GenerationRequest, SiteGenerator, finish_html
from app.generation.gemini import ModelsBusyError, QuotaExceededError
from app.generation.styles import STYLES

logger = logging.getLogger("vibeforge")

router = APIRouter()
# Routes outside /api: the public pages people share.
public_router = APIRouter()


def _build_generator() -> SiteGenerator:
    backend = os.getenv("GENERATOR", "mock").lower()
    if backend == "gemini":
        from app.generation.gemini import GeminiGenerator

        return GeminiGenerator()
    from app.generation.mock import MockGenerator

    # MOCK_DELAY slows the fake stream down to watch the live preview work.
    return MockGenerator(delay=float(os.getenv("MOCK_DELAY", "0.15")))


_generator = _build_generator()


class GenerateBody(BaseModel):
    prompt: str
    project_id: Optional[str] = None
    style: Optional[str] = None  # an id from STYLES; None = let the AI decide
    photo_ids: list[str] = []  # the person's own photos, uploaded via /photos


@router.post("/generate")
async def generate(body: GenerateBody, user: str = Depends(current_user)):
    """Streams the site as it's written, one JSON object per line:

        {"type": "status", "text": ...}   e.g. "trying another model"
        {"type": "model",  "text": ...}   which model is writing
        {"type": "text",   "text": ...}   the next piece of HTML
        {"type": "reset",  "text": ""}    model dropped out: discard the text so far
        {"type": "done", "project_id", "html", "remaining_today"}
        {"type": "error", "status", "detail"}

    Problems we can spot up front (empty prompt, daily limit, unknown
    project) are still plain HTTP errors before the stream starts.
    """
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is empty")
    if body.style is not None and body.style not in STYLES:
        raise HTTPException(status_code=400, detail="Unknown style")

    # The database calls are blocking — run them off the event loop so one
    # request never stalls the others.
    if await run_in_threadpool(usage.remaining_today, user) == 0:
        raise HTTPException(
            status_code=429,
            detail=f"You've used all {usage.DAILY_LIMIT} free generations for "
            "today — more tomorrow.",
        )

    previous_html = None
    if body.project_id:
        try:
            project = await run_in_threadpool(projects.get_project, body.project_id, user)
        except KeyError:
            raise HTTPException(status_code=404, detail="Project not found")
        previous_html = project["html"]

    if len(body.photo_ids) > user_photos.MAX_PER_SITE:
        raise HTTPException(
            status_code=400,
            detail=f"You can add up to {user_photos.MAX_PER_SITE} photos per site",
        )
    try:
        attached = await run_in_threadpool(user_photos.for_generation, user, body.photo_ids)
    except KeyError:
        raise HTTPException(status_code=404, detail="Photo not found")

    request = GenerationRequest(
        prompt=body.prompt,
        previous_html=previous_html,
        style=STYLES.get(body.style) if body.style else None,
        photos=attached,
    )
    return StreamingResponse(
        _generation_events(request, body, user), media_type="application/x-ndjson"
    )


async def _generation_events(
    request: GenerationRequest, body: GenerateBody, user: str
) -> AsyncIterator[str]:
    model, parts = "unknown", []
    try:
        async for kind, value in _generator.stream(request):
            if kind == "model":
                model = value
            elif kind == "text":
                parts.append(value)
            elif kind == "reset":
                parts.clear()
            yield _line({"type": kind, "text": value})

        html = finish_html("".join(parts))
        if "data-photo" in html:
            yield _line({"type": "status", "text": "Adding photos…"})
            html = await run_in_threadpool(photos.fill, html)
        elif "vf-photo-credits" in html:
            # Every stock photo is gone (e.g. "only my own photos"): drop
            # the credit line naming their authors too.
            html = await run_in_threadpool(photos.fill, html)
        if body.project_id:
            await run_in_threadpool(
                projects.update_project, body.project_id, user, html, body.prompt
            )
            project_id = body.project_id
        else:
            project_id = await run_in_threadpool(
                projects.create_project, user, html, body.prompt
            )
        await run_in_threadpool(user_photos.mark_sent, user, body.photo_ids, project_id)
        await run_in_threadpool(versions.add, project_id, user, body.prompt, html)
        # Only a site that was actually delivered and saved counts.
        await run_in_threadpool(usage.record, user, model)
        remaining = await run_in_threadpool(usage.remaining_today, user)
    except QuotaExceededError as e:
        logger.warning("Gemini daily quota exceeded")
        yield _line({"type": "error", "status": 429, "detail": str(e)})
        return
    except ModelsBusyError as e:
        logger.warning("All models busy")
        yield _line({"type": "error", "status": 503, "detail": str(e)})
        return
    except Exception as e:
        logger.exception("Generation failed (%s): %s", type(e).__name__, e)
        yield _line({"type": "error", "status": 500, "detail": f"{type(e).__name__}: {e}"})
        return

    # The AI sometimes leaves a photo out; say which, so the person can ask
    # for it (numbered in the order they attached them).
    unused = [n for n, p in enumerate(request.photos, start=1) if p.url not in html]
    yield _line(
        {
            "type": "done",
            "project_id": project_id,
            "html": html,
            "remaining_today": remaining,
            "unused_photos": unused,
        }
    )


def _line(event: dict) -> str:
    return json.dumps(event) + "\n"


# The handlers below are plain `def`, not `async def`, on purpose: the
# database calls block, and FastAPI runs sync handlers in a thread pool —
# so they don't freeze other requests.
@router.get("/usage")
def get_usage(user: str = Depends(current_user)):
    return {"limit": usage.limit_for(user), "remaining_today": usage.remaining_today(user)}


@router.get("/projects")
def list_projects(user: str = Depends(current_user)):
    return {"items": projects.list_projects(user)}


@router.get("/projects/{project_id}")
def get_project(project_id: str, user: str = Depends(current_user)):
    try:
        project = projects.get_project(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    slug = publishing.slug_for(project_id, user)
    return {**project, "published_url": publishing.public_url(slug) if slug else None}


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, user: str = Depends(current_user)):
    try:
        projects.get_project(project_id, user)  # only the owner's photos go
        user_photos.forget_project(user, project_id)
        projects.delete_project(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    publishing.forget_project(project_id)
    versions.forget_project(project_id)
    return {"status": "deleted"}


class RenameBody(BaseModel):
    name: Optional[str] = None


@router.patch("/projects/{project_id}")
def rename_project(project_id: str, body: RenameBody, user: str = Depends(current_user)):
    name = (body.name or "").strip()
    if len(name) > 80:
        raise HTTPException(status_code=400, detail="Name is too long (80 characters at most)")
    try:
        projects.rename_project(project_id, user, name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"name": name or None}


@router.delete("/account")
def delete_account(user: str = Depends(current_user)):
    """Delete the signed-in user's account and everything in it, at once."""
    user_photos.forget_user(user)  # files aren't deleted by the database cascade
    if supabase.config():
        auth.delete_account(user)
    else:
        for project_id in projects.delete_all(user):
            publishing.forget_project(project_id)
            versions.forget_project(project_id)
    return {"status": "deleted"}


@router.post("/photos")
async def upload_photo(
    request: Request, project_id: Optional[str] = None, user: str = Depends(current_user)
):
    """One of the person's own photos for a site, as the raw image body
    (already shrunk by the browser). Returns {"id", "url"}."""
    data = await request.body()
    mime = request.headers.get("content-type", "")
    try:
        return await run_in_threadpool(user_photos.add, user, data, mime, project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    except user_photos.PhotoError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/photos/{photo_id}")
def remove_photo(photo_id: str, user: str = Depends(current_user)):
    try:
        user_photos.remove(user, photo_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Photo not found")
    return {"status": "deleted"}


@router.get("/uploads/{path:path}")
def uploaded_photo(path: str):
    """Photos uploaded in local mode (in production they come from Supabase)."""
    file = user_photos.local_file(path)
    if file is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(file)


class TextEditBody(BaseModel):
    html: str


# Hand edits are whole pages too; anything near this size isn't one.
_MAX_EDIT_BYTES = 1_000_000


@router.post("/projects/{project_id}/text-edit")
def save_text_edit(project_id: str, body: TextEditBody, user: str = Depends(current_user)):
    """Save text the user changed by hand in the preview — a new version,
    no AI involved, so it doesn't count towards the daily limit."""
    if len(body.html.encode()) > _MAX_EDIT_BYTES or "<" not in body.html:
        raise HTTPException(status_code=400, detail="That doesn't look like this site's page")
    prompt = "✎ Edited text by hand"
    try:
        projects.update_project(project_id, user, body.html, prompt)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    versions.add(project_id, user, prompt, body.html)
    return projects.get_project(project_id, user)


@router.get("/projects/{project_id}/versions")
def list_versions(project_id: str, user: str = Depends(current_user)):
    try:
        return {"items": versions.list_versions(project_id, user)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/projects/{project_id}/versions/{version_id}")
def get_version(project_id: str, version_id: int, user: str = Depends(current_user)):
    try:
        return versions.get_version(project_id, user, version_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Version not found")


@router.post("/projects/{project_id}/versions/{version_id}/restore")
def restore_version(project_id: str, version_id: int, user: str = Depends(current_user)):
    """Bring back an earlier version as the newest one. Free: no AI involved,
    so it doesn't count towards the daily limit."""
    try:
        return versions.restore(project_id, user, version_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Version not found")


@router.post("/projects/{project_id}/publish")
def publish_project(project_id: str, user: str = Depends(current_user)):
    """Publish the project's current version (again, if it already is)."""
    try:
        slug = publishing.publish(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"published_url": publishing.public_url(slug)}


@router.delete("/projects/{project_id}/publish")
def unpublish_project(project_id: str, user: str = Depends(current_user)):
    try:
        publishing.unpublish(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"published_url": None}


@public_router.get("/s/{slug}", response_class=HTMLResponse)
def published_page(slug: str):
    """A published site, for anyone. Production serves these from Vercel
    (frontend/api/site.ts); this is the same page for local development."""
    html = publishing.page(slug)
    if html is None:
        raise HTTPException(status_code=404, detail="This page doesn't exist or was unpublished")
    return HTMLResponse(html, headers={"Content-Security-Policy": publishing.SANDBOX_CSP})
