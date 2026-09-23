import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import projects
from app.auth import current_user
from app.generation.base import GenerationRequest, SiteGenerator
from app.generation.gemini import QuotaExceededError

logger = logging.getLogger("vibeforge")

router = APIRouter()


def _build_generator() -> SiteGenerator:
    backend = os.getenv("GENERATOR", "mock").lower()
    if backend == "gemini":
        from app.generation.gemini import GeminiGenerator

        return GeminiGenerator()
    from app.generation.mock import MockGenerator

    return MockGenerator()


_generator = _build_generator()


class GenerateBody(BaseModel):
    prompt: str
    project_id: Optional[str] = None


@router.post("/generate")
async def generate(body: GenerateBody, user: str = Depends(current_user)):
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is empty")

    previous_html = None
    if body.project_id:
        try:
            previous_html = projects.get_project(body.project_id, user)["html"]
        except KeyError:
            raise HTTPException(status_code=404, detail="Project not found")

    request = GenerationRequest(prompt=body.prompt, previous_html=previous_html)
    try:
        result = _generator.generate(request)
    except QuotaExceededError as e:
        logger.warning("Gemini daily quota exceeded")
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.exception("Generation failed (%s): %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    if body.project_id:
        projects.update_project(body.project_id, user, result.html, body.prompt)
        project_id = body.project_id
    else:
        project_id = projects.create_project(user, result.html, body.prompt)

    return {"project_id": project_id, "html": result.html}


@router.get("/projects")
async def list_projects(user: str = Depends(current_user)):
    return {"items": projects.list_projects(user)}


@router.get("/projects/{project_id}")
async def get_project(project_id: str, user: str = Depends(current_user)):
    try:
        return projects.get_project(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: str = Depends(current_user)):
    try:
        projects.delete_project(project_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted"}
