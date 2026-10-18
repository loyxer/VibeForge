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

import asyncio  # noqa: E402
import threading  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.api.routes import public_router, router  # noqa: E402

# How long a stop waits for sites still being made (seconds) — a little under
# the longest shutdown delay Render allows (300; not available on the free plan).
SHUTDOWN_WAIT = 280


@asynccontextmanager
async def lifespan(_app):
    # Point the Telegram bot at this server — in the background, so starting
    # up never waits on Telegram.
    from app import leads

    threading.Thread(target=leads.register_webhook, daemon=True).start()
    yield
    # Shutting down (a new version is going live): uvicorn already lets open
    # requests, such as a site being streamed, finish. Sites being made for a
    # Telegram chat run outside any request, so wait for them here — Render
    # stops the process for good after its own delay (see README).
    from app.api import routes

    pending = list(routes._chat_tasks)
    if pending:
        _log.info("Shutting down: waiting for %d Telegram site(s)", len(pending))
        await asyncio.wait(pending, timeout=SHUTDOWN_WAIT)


app = FastAPI(title="VibeForge API", lifespan=lifespan)

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
app.include_router(public_router)


@app.get("/health")
def health():
    from app.api import routes

    return {"status": "ok", "generating": routes.generating_now()}
