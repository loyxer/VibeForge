"""Project store: each project is one generated site plus the prompt
history that built it, owned by one user.

Two backends behind the same functions:
- Supabase Postgres (table from backend/supabase/schema.sql) when
  SUPABASE_URL + SUPABASE_SECRET_KEY are set — survives Render restarts.
- A local JSON file otherwise, for plain local dev without any keys.

Every function raises KeyError when the project doesn't exist or belongs
to someone else, so callers can't tell the two apart.
"""
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import supabase
from app.auth import LOCAL_USER
from app.supabase import rest as _rest

# ---------------------------------------------------------------- Supabase


def _as_uuid(project_id: str) -> str:
    try:
        return str(uuid.UUID(project_id))
    except ValueError:
        raise KeyError(project_id)


def _sb_get(config, project_id: str, owner: str) -> dict[str, Any]:
    with _rest(config) as client:
        res = client.get(
            "/projects",
            params={
                "id": f"eq.{_as_uuid(project_id)}",
                "user_id": f"eq.{owner}",
                "select": "html,history",
            },
        )
    res.raise_for_status()
    rows = res.json()
    if not rows:
        raise KeyError(project_id)
    return rows[0]


def _sb_create(config, owner: str, html: str, prompt: str) -> str:
    with _rest(config) as client:
        res = client.post(
            "/projects",
            json={"user_id": owner, "html": html, "history": [prompt]},
            headers={"Prefer": "return=representation"},
        )
    res.raise_for_status()
    return res.json()[0]["id"]


def _sb_update(config, project_id: str, owner: str, html: str, prompt: str) -> None:
    history = _sb_get(config, project_id, owner)["history"]
    with _rest(config) as client:
        res = client.patch(
            "/projects",
            params={"id": f"eq.{_as_uuid(project_id)}", "user_id": f"eq.{owner}"},
            json={
                "html": html,
                "history": [*history, prompt],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    res.raise_for_status()


def _sb_list(config, owner: str) -> list[dict[str, Any]]:
    with _rest(config) as client:
        res = client.get(
            "/projects",
            params={
                "user_id": f"eq.{owner}",
                "select": "id,history",
                "order": "updated_at.desc",
            },
        )
    res.raise_for_status()
    return res.json()


def _sb_delete(config, project_id: str, owner: str) -> None:
    with _rest(config) as client:
        res = client.delete(
            "/projects",
            params={"id": f"eq.{_as_uuid(project_id)}", "user_id": f"eq.{owner}"},
            headers={"Prefer": "return=representation"},
        )
    res.raise_for_status()
    if not res.json():
        raise KeyError(project_id)


# --------------------------------------------------------------- JSON file

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


def _owner_of(project: dict[str, Any]) -> str:
    # Projects saved before accounts existed have no owner — they belong to
    # the single local user.
    return project.get("owner", LOCAL_USER)


def _owned(data: dict[str, Any], project_id: str, owner: str) -> dict[str, Any]:
    project = data.get(project_id)
    if project is None or _owner_of(project) != owner:
        raise KeyError(project_id)
    return project


# ------------------------------------------------------------------ public


def create_project(owner: str, html: str, prompt: str) -> str:
    if config := supabase.config():
        return _sb_create(config, owner, html, prompt)
    with _lock:
        data = _read()
        project_id = uuid.uuid4().hex
        data[project_id] = {"owner": owner, "html": html, "history": [prompt]}
        _write(data)
        return project_id


def update_project(project_id: str, owner: str, html: str, prompt: str) -> None:
    if config := supabase.config():
        return _sb_update(config, project_id, owner, html, prompt)
    with _lock:
        data = _read()
        project = _owned(data, project_id, owner)
        project["html"] = html
        project["history"].append(prompt)
        _write(data)


def get_project(project_id: str, owner: str) -> dict[str, Any]:
    if config := supabase.config():
        return _sb_get(config, project_id, owner)
    with _lock:
        project = _owned(_read(), project_id, owner)
        return {"html": project["html"], "history": project["history"]}


def list_projects(owner: str) -> list[dict[str, Any]]:
    if config := supabase.config():
        return _sb_list(config, owner)
    with _lock:
        return [
            {"id": pid, "history": p["history"]}
            for pid, p in _read().items()
            if _owner_of(p) == owner
        ]


def delete_project(project_id: str, owner: str) -> None:
    if config := supabase.config():
        return _sb_delete(config, project_id, owner)
    with _lock:
        data = _read()
        _owned(data, project_id, owner)
        del data[project_id]
        _write(data)
