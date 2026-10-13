import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import projects, usage
from app.auth import current_user
from app.generation.base import GenerationRequest, SiteGenerator, finish_html
from app.generation.gemini import ModelsBusyError, QuotaExceededError
from app.generation.styles import STYLES

logger = logging.getLogger("vibeforge")

router = APIRouter()


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

    request = GenerationRequest(
        prompt=body.prompt,
        previous_html=previous_html,
        style=STYLES.get(body.style) if body.style else None,
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
        if body.project_id:
            await run_in_threadpool(
                projects.update_project, body.project_id, user, html, body.prompt
            )
            project_id = body.project_id
        else:
            project_id = await run_in_threadpool(
                projects.create_project, user, html, body.prompt
            )
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

    yield _line(
        {"type": "done", "project_id": project_id, "html": html, "remaining_today": remaining}
    )


def _line(event: dict) -> str:
    return json.dumps(event) + "\n"


# The handlers below are plain `def`, not `async def`, on purpose: the
# database calls block, and FastAPI runs sync handlers in a thread pool —
# so they don't freeze other requests.
@router.get("/usage")
def get_usage(user: str = Depends(current_user)):
    return {"limit": usage.DAILY_LIMIT or None, "remaining_today": usage.remaining_today(user)}


@router.get("/projects")
def list_projects(user: str = Depends(current_user)):
    return {"items": projects.list_projects(user)}


@router.get("/projects/{project_id}")
def get_project(project_id: str, user: str = Depends(current_user)):
    try:
        return projects.get_project(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, user: str = Depends(current_user)):
    try:
        projects.delete_project(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted"}
