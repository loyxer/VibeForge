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

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
