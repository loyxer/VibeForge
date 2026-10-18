import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from app import auth, chat_sites, feedback, leads, logos, photos, projects, publishing, reviews, stats, supabase, usage, user_photos, versions, visits
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
    bilingual: bool = False  # Ukrainian + English with a language switcher
    pages: bool = False  # several pages in one file with a menu


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
        bilingual=body.bilingual,
        pages=body.pages,
    )
    return StreamingResponse(
        _generation_events(request, body, user), media_type="application/x-ndjson"
    )


# How many sites are being made right now, shown by /health: Render's free
# plan stops the old version 90 seconds after a deploy, whatever is running,
# so look at this before pushing (see README).
_generating = 0


def generating_now() -> int:
    return _generating


async def _generation_events(
    request: GenerationRequest, body: GenerateBody, user: str
) -> AsyncIterator[str]:
    global _generating
    _generating += 1
    try:
        async for line in _run_generation(request, body, user):
            yield line
    finally:
        _generating -= 1


async def _run_generation(
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
    return {
        "limit": usage.limit_for(user),
        "remaining_today": usage.remaining_today(user),
        "owner": auth.is_owner(user),  # shows the Stats item in the account menu
    }


@router.get("/stats")
def get_stats(user: str = Depends(current_user)):
    """How VibeForge is used — for the owner only."""
    if not auth.is_owner(user):
        raise HTTPException(status_code=403, detail="Only the owner can see this")
    return stats.overview()


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
    leads.forget_project(project_id)
    visits.forget_project(project_id)
    reviews.forget_project(project_id)
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
            reviews.forget_project(project_id)
    return {"status": "deleted"}


@router.post("/forms/{slug}")
async def form_submitted(slug: str, request: Request):
    """A visitor sent a form on a published site (the page's own script
    posts it here as text/plain JSON, so no CORS preflight is needed).
    Public: there's no sign-in on published pages."""
    body = await request.body()
    if len(body) > 20_000:
        raise HTTPException(status_code=413, detail="Too large")
    try:
        fields = json.loads(body).get("fields")
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Bad form data")
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
    try:
        await run_in_threadpool(leads.submit, slug, fields, ip)
    except KeyError:
        raise HTTPException(status_code=404, detail="This page doesn't exist or was unpublished")
    except leads.TooMany:
        raise HTTPException(status_code=429, detail="Too many submissions — try again later")
    return {"status": "received"}


@router.post("/pages/{slug}/seen")
def page_visited(slug: str, request: Request):
    """Someone opened a published page (its own one-line script calls this).
    Public, and quiet: a visitor's page never needs an answer."""
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
    try:
        visits.record(slug, ip, request.headers.get("user-agent", ""))
    except KeyError:
        raise HTTPException(status_code=404, detail="This page doesn't exist or was unpublished")
    return {"status": "counted"}


@router.get("/projects/{project_id}/visits")
def project_visits(project_id: str, user: str = Depends(current_user)):
    try:
        projects.get_project(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    return visits.summary(project_id, user)


class FeedbackBody(BaseModel):
    kind: str
    message: str
    email: str = ""


@router.post("/feedback")
def send_feedback(body: FeedbackBody, user: str = Depends(current_user)):
    """A support request or an idea for the owner."""
    try:
        feedback.submit(user, body.email, body.kind, body.message)
    except feedback.Invalid as e:
        raise HTTPException(status_code=400, detail=str(e))
    except feedback.TooMany:
        raise HTTPException(status_code=429, detail="Too many messages — please try again later")
    return {"sent": True}


@router.get("/telegram")
def telegram_status(user: str = Depends(current_user)):
    return leads.status(user)


@router.post("/telegram/link")
def telegram_link(user: str = Depends(current_user)):
    """A one-time link to the bot; opening it and pressing Start connects."""
    if not leads.bot_token():
        raise HTTPException(status_code=503, detail="Telegram isn't available right now")
    return {"url": leads.link_url(user)}


@router.delete("/telegram")
def telegram_disconnect(user: str = Depends(current_user)):
    leads.disconnect(user)
    return {"connected": False}


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Messages to the bot. Only Telegram knows the secret it sends."""
    if not leads.bot_token() or request.headers.get(
        "x-telegram-bot-api-secret-token"
    ) != leads.webhook_secret():
        raise HTTPException(status_code=403, detail="Forbidden")
    update = await request.json()
    job = await run_in_threadpool(chat_sites.handle_update, update)
    if job:
        # Telegram wants its answer within seconds; the site takes minutes.
        task = asyncio.create_task(_build_for_chat(job))
        _chat_tasks.add(task)  # a task nobody holds can be garbage-collected mid-run
        task.add_done_callback(_chat_tasks.discard)
    return {"ok": True}


_chat_tasks: set[asyncio.Task] = set()


async def _build_for_chat(job: chat_sites.Job) -> None:
    """Make (or change) the site a person asked for in the Telegram chat, then
    tell them. The same pipeline as the app's chat: limits, saving, history."""
    typing = asyncio.create_task(_keep_typing(job.chat_id))
    done: Optional[dict] = None
    error_status = 500
    try:
        previous_html = None
        if job.project_id:
            project = await run_in_threadpool(projects.get_project, job.project_id, job.owner)
            previous_html = project["html"]
        request = GenerationRequest(prompt=job.prompt, previous_html=previous_html)
        body = GenerateBody(prompt=job.prompt, project_id=job.project_id)
        async for line in _generation_events(request, body, job.owner):
            event = json.loads(line)
            if event["type"] == "done":
                done = event
            elif event["type"] == "error":
                error_status = event.get("status", 500)
    except Exception:
        logger.exception("Telegram site failed")
    finally:
        typing.cancel()
    if done:
        await run_in_threadpool(
            chat_sites.finished, job, done["project_id"], done["remaining_today"]
        )
    else:
        await run_in_threadpool(chat_sites.failed, job, error_status)


async def _keep_typing(chat_id: int) -> None:
    while True:
        await run_in_threadpool(leads.typing, chat_id)
        await asyncio.sleep(4)


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
    # Own photos the person swapped in while editing (already uploaded).
    photo_ids: list[str] = []


# Hand edits are whole pages too; anything near this size isn't one.
_MAX_EDIT_BYTES = 1_000_000


@router.post("/projects/{project_id}/text-edit")
def save_text_edit(project_id: str, body: TextEditBody, user: str = Depends(current_user)):
    """Save what the user changed by hand in the preview (text, colors,
    photos, links) — a new version, no AI involved, so it doesn't count
    towards the daily limit."""
    if len(body.html.encode()) > _MAX_EDIT_BYTES or "<" not in body.html:
        raise HTTPException(status_code=400, detail="That doesn't look like this site's page")
    if len(body.photo_ids) > user_photos.MAX_PER_SITE:
        raise HTTPException(status_code=400, detail="Too many photos")
    prompt = "✎ Edited by hand"
    # A stock photo swapped for the person's own no longer needs its credit.
    html = photos.refresh_credits(body.html) if "vf-photo-credits" in body.html else body.html
    try:
        projects.update_project(project_id, user, html, prompt)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    user_photos.mark_sent(user, body.photo_ids, project_id)
    versions.add(project_id, user, prompt, html)
    return projects.get_project(project_id, user)


class LogoBody(BaseModel):
    name: str
    brief: str = ""  # what the business does, style and colors wanted
    dark: bool = False  # the logo goes on a dark header


class LogoSaveBody(BaseModel):
    svg: str


@router.post("/logos")
def make_logos(body: LogoBody, user: str = Depends(current_user)):
    """Three logo concepts, drawn as SVG by the free AI model — a small
    request, so it doesn't count towards the daily generations."""
    try:
        return {"logos": logos.make(body.name, body.brief, body.dark, user)}
    except logos.TooMany as e:
        raise HTTPException(status_code=429, detail=str(e))
    except logos.LogoError as e:
        if str(e).startswith("Write"):
            raise HTTPException(status_code=400, detail=str(e))
        logger.warning("Logos failed: %s", e)
        raise HTTPException(
            status_code=503, detail="The AI is busy right now — try again in a minute"
        )


@router.post("/projects/{project_id}/logo")
def save_logo(project_id: str, body: LogoSaveBody, user: str = Depends(current_user)):
    """Put a chosen logo into the site's header — a new version, no AI."""
    try:
        html = projects.get_project(project_id, user)["html"]
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        html = logos.with_logo(html, body.svg)
    except logos.LogoError as e:
        raise HTTPException(status_code=400, detail=str(e))
    prompt = "🎨 Added logo"
    projects.update_project(project_id, user, html, prompt)
    versions.add(project_id, user, prompt, html)
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


class SeoBody(BaseModel):
    indexable: bool


@router.get("/projects/{project_id}/seo")
def get_seo(project_id: str, user: str = Depends(current_user)):
    """Whether search engines may list the published page."""
    try:
        projects.get_project(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"indexable": publishing.is_indexable(project_id, user)}


@router.put("/projects/{project_id}/seo")
def set_seo(project_id: str, body: SeoBody, user: str = Depends(current_user)):
    try:
        projects.get_project(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    if not publishing.set_indexable(project_id, user, body.indexable):
        raise HTTPException(status_code=409, detail="Publish the site first")
    return {"indexable": body.indexable}


@public_router.get("/s/{slug}", response_class=HTMLResponse)
def published_page(slug: str):
    """A published site, for anyone. Production serves these from Vercel
    (frontend/api/site.ts); this is the same page for local development."""
    html = publishing.page(slug)
    if html is None:
        raise HTTPException(status_code=404, detail="This page doesn't exist or was unpublished")
    headers = {"Content-Security-Policy": publishing.SANDBOX_CSP}
    if not publishing.is_slug_indexable(slug):
        headers["X-Robots-Tag"] = "noindex"
    return HTMLResponse(html, headers=headers)


# ----------------------------------------------- a link for the client


def _review_url(token: str) -> str:
    base = os.getenv("FRONTEND_ORIGIN", "").rstrip("/") or "http://localhost:5173"
    return f"{base}/r/{token}"


def _review_state(project_id: str, user: str) -> dict:
    token = reviews.token_of(project_id, user)
    return {
        "url": _review_url(token) if token else None,
        "comments": reviews.comments(project_id, user),
    }


@router.get("/projects/{project_id}/review")
def get_review(project_id: str, user: str = Depends(current_user)):
    try:
        return _review_state(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/projects/{project_id}/review")
def start_review(project_id: str, user: str = Depends(current_user)):
    """Switch on the client's link (the same link if it's already on)."""
    try:
        reviews.enable(project_id, user)
        return _review_state(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.delete("/projects/{project_id}/review")
def stop_review(project_id: str, user: str = Depends(current_user)):
    """Switch the link off; comments already left stay."""
    try:
        reviews.disable(project_id, user)
        return _review_state(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


class ResolveBody(BaseModel):
    resolved: bool


@router.patch("/projects/{project_id}/review/comments/{comment_id}")
def resolve_comment(project_id: str, comment_id: int, body: ResolveBody, user: str = Depends(current_user)):
    try:
        reviews.set_resolved(project_id, user, comment_id, body.resolved)
        return _review_state(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Comment not found")


@router.delete("/projects/{project_id}/review/comments/{comment_id}")
def remove_comment(project_id: str, comment_id: int, user: str = Depends(current_user)):
    try:
        reviews.delete_comment(project_id, user, comment_id)
        return _review_state(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/reviews/{token}")
def review_page(token: str):
    """What the client's page shows. Public: the token is the key."""
    try:
        return reviews.view(token)
    except KeyError:
        raise HTTPException(status_code=404, detail="This link doesn't exist or was switched off")


class CommentBody(BaseModel):
    author: str = ""
    text: str
    selector: str = ""
    label: str = ""


@router.post("/reviews/{token}/comments")
def add_review_comment(token: str, body: CommentBody, request: Request):
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
    try:
        return reviews.add_comment(
            token, body.author, body.text, body.selector, body.label, f"{ip}|{request.headers.get('user-agent', '')}"
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="This link doesn't exist or was switched off")
    except reviews.Invalid as e:
        raise HTTPException(status_code=400, detail=str(e))
    except reviews.TooMany:
        raise HTTPException(status_code=429, detail="Too many comments — please try again later")
