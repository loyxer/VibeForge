import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Our own log lines (which model generated a site, quota fallbacks, errors)
# at INFO, without turning on INFO noise from every library.
_log = logging.getLogger("vibeforge")
_log.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
_log.addHandler(_handler)
_log.propagate = False

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.api.routes import router  # noqa: E402

app = FastAPI(title="VibeForge API")

# FRONTEND_ORIGIN is the deployed frontend's real URL (e.g.
# https://vibeforge.vercel.app) — set it as an env var on the hosting
# platform. localhost:5173 stays allowed so local dev keeps working.
_allow_origins = ["http://localhost:5173"]
if frontend_origin := os.getenv("FRONTEND_ORIGIN"):
    _allow_origins.append(frontend_origin)

# Bump together with API_VERSION in frontend/src/api.ts whenever the API
# changes in a way an already-open old page can't handle. That page then
# tells the user to refresh instead of failing with a cryptic error.
API_VERSION = "2"


class ApiVersionHeader:
    """Adds X-API-Version to every response. Plain ASGI on purpose: unlike
    @app.middleware("http"), it never buffers the streamed generation."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_version(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-api-version", API_VERSION.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_version)


app.add_middleware(ApiVersionHeader)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-API-Version"],  # readable by the frontend's JS
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
