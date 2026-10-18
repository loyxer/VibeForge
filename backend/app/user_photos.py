"""Photos people upload for their own sites (a client's café, their products).

The browser shrinks each photo first (about 1600px, a few hundred KB), then
it's stored in Supabase Storage — the public bucket "site-photos", one
folder per user — or, without Supabase, in backend/data/uploads, served by
/api/uploads/... A row per photo (table `site_photos`, or data/photos.json)
remembers whose it is and which site it was added to, so deleting a site
or an account deletes its photos too.

They go into the page as plain <img src="..."> with their public URL: no
data-photo attribute, so photos.py leaves them alone and they get no
Unsplash credit line — they're the user's own.
"""
import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from app import projects, supabase
from app.supabase import rest as _rest

MAX_PER_SITE = 10
MAX_BYTES = 2_000_000  # after the browser has shrunk it; typically ~300 KB
MAX_PER_USER = 100  # keeps the free 1 GB of storage safe from one account
BUCKET = "site-photos"
_PENDING_FOR = timedelta(days=1)  # uploaded but never sent: cleaned up after this
_TYPES = {"image/webp": ".webp", "image/jpeg": ".jpg", "image/png": ".png"}


class PhotoError(ValueError):
    """Something the person can fix (wrong file, too many photos)."""


@dataclass
class AttachedPhoto:
    id: str
    url: str
    data: bytes
    mime: str


def add(owner: str, data: bytes, mime: str, project_id: Optional[str]) -> dict[str, str]:
    """Store an uploaded photo for a site (None = a site not created yet).
    Returns {"id", "url"}. KeyError if the project isn't the owner's."""
    mime = mime.split(";")[0].strip().lower()
    if mime not in _TYPES or _sniff(data) != mime:
        raise PhotoError("That file isn't a photo we can use (JPEG, PNG or WebP)")
    if len(data) > MAX_BYTES:
        raise PhotoError("That photo is too large")
    html = projects.get_project(project_id, owner)["html"] if project_id else ""

    _drop_stale_pending(owner)
    rows = _rows(owner)
    if len(rows) >= MAX_PER_USER:
        raise PhotoError("You've reached the photo limit for your account")
    if _count_for_site(rows, project_id, html) >= MAX_PER_SITE:
        raise PhotoError(f"You can add up to {MAX_PER_SITE} photos per site")

    photo_id = str(uuid.uuid4())
    path = f"{owner}/{photo_id}{_TYPES[mime]}"
    _store_file(path, data, mime)
    _insert({"id": photo_id, "owner": owner, "project_id": project_id, "path": path})
    return {"id": photo_id, "url": public_url(path)}


def for_generation(owner: str, ids: list[str]) -> list[AttachedPhoto]:
    """The photos sent with a request, in order, with their bytes so the AI
    can see them. KeyError if any isn't the owner's."""
    by_id = {r["id"]: r for r in _rows(owner)}
    photos = []
    for photo_id in ids:
        row = by_id.get(photo_id)
        if row is None:
            raise KeyError(photo_id)
        mime = next(m for m, ext in _TYPES.items() if row["path"].endswith(ext))
        photos.append(AttachedPhoto(photo_id, public_url(row["path"]), _read_file(row["path"]), mime))
    return photos


def mark_sent(owner: str, ids: list[str], project_id: str) -> None:
    """The photos went into a generation for this site."""
    if not ids:
        return
    if config := supabase.config():
        with _rest(config) as client:
            res = client.patch(
                "/site_photos",
                params={"id": f"in.({','.join(ids)})", "user_id": f"eq.{owner}"},
                json={"project_id": project_id, "sent": True},
            )
        res.raise_for_status()
        return
    with _lock:
        rows = _read()
        for r in rows:
            if r["id"] in ids and r["owner"] == owner:
                r.update(project_id=project_id, sent=True)
        _write(rows)


def remove(owner: str, photo_id: str) -> None:
    """Take back a photo that hasn't been sent yet (the × on its thumbnail)."""
    row = next((r for r in _rows(owner) if r["id"] == photo_id), None)
    if row is None or row["sent"]:
        raise KeyError(photo_id)
    _delete([row])


def forget_project(owner: str, project_id: str) -> None:
    """Delete a site's photos — call before deleting the site itself."""
    _delete([r for r in _rows(owner) if r["project_id"] == project_id])


def forget_user(owner: str) -> None:
    """Delete all of an account's photos — call before deleting the account."""
    _delete(_rows(owner))


def public_url(path: str) -> str:
    if config := supabase.config():
        return f"{config[0]}/storage/v1/object/public/{BUCKET}/{path}"
    return f"/api/uploads/{path}"


def local_file(path: str) -> Optional[Path]:
    """A locally stored photo for /api/uploads (local mode only)."""
    file = (_UPLOADS / path).resolve()
    if supabase.config() or not file.is_relative_to(_UPLOADS.resolve()) or not file.is_file():
        return None
    return file


# ------------------------------------------------------------------ helpers


def _sniff(data: bytes) -> Optional[str]:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _count_for_site(rows: list[dict], project_id: Optional[str], html: str) -> int:
    """Photos waiting to be sent plus those still on the page — a photo the
    person has since replaced doesn't count against them any more."""
    return sum(
        1
        for r in rows
        if r["project_id"] == project_id
        and (not r["sent"] or public_url(r["path"]) in html)
    )


def _drop_stale_pending(owner: str) -> None:
    cutoff = datetime.now(timezone.utc) - _PENDING_FOR
    _delete([r for r in _rows(owner) if not r["sent"] and r["created_at"] < cutoff])


# ------------------------------------------------- Supabase or local files

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_UPLOADS = _DATA_DIR / "uploads"
_STORE_PATH = _DATA_DIR / "photos.json"
_lock = threading.Lock()


def _storage(config) -> httpx.Client:
    url, key = config
    return httpx.Client(
        base_url=f"{url}/storage/v1",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30,
    )


def _store_file(path: str, data: bytes, mime: str) -> None:
    if config := supabase.config():
        with _storage(config) as client:
            res = client.post(
                f"/object/{BUCKET}/{path}",
                content=data,
                # On the free plan the CDN isn't told about deletions, so a
                # deleted photo stays reachable until its cache runs out:
                # keep that to an hour (the Privacy policy says so).
                headers={"Content-Type": mime, "cache-control": "max-age=3600"},
            )
        res.raise_for_status()
        return
    file = _UPLOADS / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(data)


def _read_file(path: str) -> bytes:
    if config := supabase.config():
        with _storage(config) as client:
            res = client.get(f"/object/{BUCKET}/{path}")
        res.raise_for_status()
        return res.content
    return (_UPLOADS / path).read_bytes()


def _rows(owner: str) -> list[dict[str, Any]]:
    """The owner's photos: id, owner, project_id, path, sent, created_at."""
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get(
                "/site_photos",
                params={
                    "user_id": f"eq.{owner}",
                    "select": "id,project_id,path,sent,created_at",
                    "order": "created_at.asc",
                },
            )
        res.raise_for_status()
        return [
            {**r, "owner": owner, "created_at": datetime.fromisoformat(r["created_at"])}
            for r in res.json()
        ]
    with _lock:
        return [
            {**r, "created_at": datetime.fromisoformat(r["created_at"])}
            for r in _read()
            if r["owner"] == owner
        ]


def _insert(row: dict[str, Any]) -> None:
    if config := supabase.config():
        with _rest(config) as client:
            res = client.post(
                "/site_photos",
                json={
                    "id": row["id"],
                    "user_id": row["owner"],
                    "project_id": row["project_id"],
                    "path": row["path"],
                },
            )
        res.raise_for_status()
        return
    with _lock:
        rows = _read()
        rows.append(
            {**row, "sent": False, "created_at": datetime.now(timezone.utc).isoformat()}
        )
        _write(rows)


def _delete(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    ids = {r["id"] for r in rows}
    if config := supabase.config():
        with _storage(config) as client:
            client.request(
                "DELETE", f"/object/{BUCKET}", json={"prefixes": [r["path"] for r in rows]}
            ).raise_for_status()
        with _rest(config) as client:
            client.delete(
                "/site_photos", params={"id": f"in.({','.join(ids)})"}
            ).raise_for_status()
        return
    for r in rows:
        (_UPLOADS / r["path"]).unlink(missing_ok=True)
    with _lock:
        _write([r for r in _read() if r["id"] not in ids])


def _read() -> list[dict[str, Any]]:
    if not _STORE_PATH.exists():
        return []
    return json.loads(_STORE_PATH.read_text())


def _write(rows: list[dict[str, Any]]) -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    _STORE_PATH.write_text(json.dumps(rows, indent=2))
