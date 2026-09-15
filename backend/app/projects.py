"""Simple JSON-backed project store: each project is one generated site
plus the prompt history that built it. No real database yet — fine for a
single-user local setup, swap for SQLite/Postgres once there's more than
one user.
"""
import json
import threading
import uuid
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_STORE_PATH = _DATA_DIR / "projects.json"
_lock = threading.Lock()


def _read() -> dict[str, Any]:
    if not _STORE_PATH.exists():
        return {}
    return json.loads(_STORE_PATH.read_text())


def _write(data: dict[str, Any]) -> None:
    _STORE_PATH.write_text(json.dumps(data, indent=2))


def create_project(html: str, prompt: str) -> str:
    with _lock:
        data = _read()
        project_id = uuid.uuid4().hex
        data[project_id] = {"html": html, "history": [prompt]}
        _write(data)
        return project_id


def update_project(project_id: str, html: str, prompt: str) -> None:
    with _lock:
        data = _read()
        if project_id not in data:
            raise KeyError(project_id)
        data[project_id]["html"] = html
        data[project_id]["history"].append(prompt)
        _write(data)


def get_project(project_id: str) -> dict[str, Any]:
    with _lock:
        data = _read()
        if project_id not in data:
            raise KeyError(project_id)
        return data[project_id]


def list_projects() -> list[dict[str, Any]]:
    with _lock:
        data = _read()
        return [{"id": pid, "history": p["history"]} for pid, p in data.items()]
