"""Version history of each site: one version per successful generation or
restore, oldest first. Restoring never deletes anything — it adds the old
HTML back as a new, latest version, so a restore can be undone too.

Sites created before history existed get their current state recorded as
version 1 the first time their history is asked for.

Same two backends as projects.py: the `project_versions` table in Supabase
(see backend/supabase/schema.sql) or a local JSON file.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import projects, supabase
from app.supabase import rest as _rest


def add(project_id: str, owner: str, prompt: str, html: str) -> None:
    at = datetime.now(timezone.utc).isoformat()
    if config := supabase.config():
        with _rest(config) as client:
            res = client.post(
                "/project_versions",
                json={
                    "project_id": projects._as_uuid(project_id),
                    "user_id": owner,
                    "prompt": prompt,
                    "html": html,
                    "created_at": at,
                },
            )
        res.raise_for_status()
        return
    with _lock:
        rows = _read()
        next_id = max((r["id"] for r in rows), default=0) + 1
        rows.append(
            {"id": next_id, "project_id": project_id, "owner": owner,
             "prompt": prompt, "html": html, "created_at": at}
        )
        _write(rows)


def list_versions(project_id: str, owner: str) -> list[dict[str, Any]]:
    """Newest first, each with its number (1 = the first version) — no HTML.
    Raises KeyError if the project doesn't exist or isn't the owner's."""
    project = projects.get_project(project_id, owner)
    rows = _rows(project_id, owner)
    if not rows:
        # A site from before version history: its current state is v1.
        add(project_id, owner, project["history"][-1] if project["history"] else "", project["html"])
        rows = _rows(project_id, owner)
    numbered = [
        {"id": r["id"], "number": n, "prompt": r["prompt"], "created_at": r["created_at"]}
        for n, r in enumerate(rows, start=1)
    ]
    return numbered[::-1]


def get_version(project_id: str, owner: str, version_id: int) -> dict[str, Any]:
    """{"number", "prompt", "html"} of one version; KeyError if not found."""
    projects.get_project(project_id, owner)
    for n, r in enumerate(_rows(project_id, owner, with_html=True), start=1):
        if r["id"] == version_id:
            return {"number": n, "prompt": r["prompt"], "html": r["html"]}
    raise KeyError(version_id)


def restore(project_id: str, owner: str, version_id: int) -> dict[str, Any]:
    """Make an earlier version the current one (as a new latest version).
    Returns the project's new state {"html", "history"}."""
    version = get_version(project_id, owner, version_id)
    prompt = f"↩ Restored version {version['number']}"
    projects.update_project(project_id, owner, version["html"], prompt)
    add(project_id, owner, prompt, version["html"])
    return projects.get_project(project_id, owner)


def _rows(project_id: str, owner: str, with_html: bool = False) -> list[dict[str, Any]]:
    """The project's versions, oldest first."""
    if config := supabase.config():
        columns = "id,prompt,created_at" + (",html" if with_html else "")
        with _rest(config) as client:
            res = client.get(
                "/project_versions",
                params={
                    "project_id": f"eq.{projects._as_uuid(project_id)}",
                    "user_id": f"eq.{owner}",
                    "select": columns,
                    "order": "created_at.asc,id.asc",
                },
            )
        res.raise_for_status()
        return res.json()
    with _lock:
        return [
            r for r in _read() if r["project_id"] == project_id and r["owner"] == owner
        ]


def forget_project(project_id: str) -> None:
    """Drop a deleted project's versions (Supabase does this by cascade)."""
    if supabase.config():
        return
    with _lock:
        _write([r for r in _read() if r["project_id"] != project_id])


# --------------------------------------------------------------- JSON file

_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "versions.json"
_lock = threading.Lock()


def _read() -> list[dict[str, Any]]:
    if not _STORE_PATH.exists():
        return []
    return json.loads(_STORE_PATH.read_text())


def _write(rows: list[dict[str, Any]]) -> None:
    _STORE_PATH.parent.mkdir(exist_ok=True)
    _STORE_PATH.write_text(json.dumps(rows, indent=2))
