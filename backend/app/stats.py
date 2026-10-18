"""Numbers for the owner: how many people use VibeForge and how.

Only the owner's accounts may see this (auth.is_owner). Emails are shown
half-hidden — enough to recognise someone, not to copy a list of addresses.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app import projects, publishing, supabase, usage, user_photos
from app.auth import LOCAL_USER
from app.supabase import rest as _rest


def overview() -> dict[str, Any]:
    raw = _supabase_rows() if supabase.config() else _local_rows()
    return summarize(**raw, now=datetime.now(timezone.utc), today=usage.start_of_today())


def summarize(users, generations, sites, published, photos, now, today) -> dict[str, Any]:
    """All rows carry user_id; dates are timezone-aware datetimes (or None)."""
    week, month = now - timedelta(days=7), now - timedelta(days=30)
    gens_by_user = Counter(g["user_id"] for g in generations)
    sites_by_user = Counter(s["user_id"] for s in sites)
    last_gen: dict[str, datetime] = {}
    for g in generations:
        if g["user_id"] not in last_gen or g["created_at"] > last_gen[g["user_id"]]:
            last_gen[g["user_id"]] = g["created_at"]

    people = []
    for u in users:
        last_active = max(
            (d for d in (last_gen.get(u["id"]), u.get("last_sign_in_at")) if d), default=None
        )
        people.append(
            {
                "email": mask_email(u.get("email") or ""),
                "owner": u["id"] in usage.UNLIMITED or u["id"] == LOCAL_USER,
                "joined": _iso(u.get("created_at")),
                "last_active": _iso(last_active),
                "sites": sites_by_user[u["id"]],
                "generations": gens_by_user[u["id"]],
            }
        )
    people.sort(key=lambda p: p["last_active"] or "", reverse=True)

    return {
        "users": {
            "total": len(users),
            "new_7d": sum(1 for u in users if u.get("created_at") and u["created_at"] >= week),
            "active_7d": len({g["user_id"] for g in generations if g["created_at"] >= week}),
        },
        "sites": {"total": len(sites), "published": len(published)},
        "generations": {
            "today": sum(1 for g in generations if g["created_at"] >= today),
            "last_7d": sum(1 for g in generations if g["created_at"] >= week),
            "last_30d": sum(1 for g in generations if g["created_at"] >= month),
            "total": len(generations),
        },
        "models_7d": [
            {"model": m, "count": n}
            for m, n in Counter(
                g["model"] for g in generations if g["created_at"] >= week
            ).most_common()
        ],
        "photos": {"total": len(photos)},
        "people": people,
    }


def mask_email(email: str) -> str:
    name, at, domain = email.partition("@")
    if not at:
        return email
    return f"{name[:2]}***@{domain}"


def _iso(d: Optional[datetime]) -> Optional[str]:
    return d.isoformat() if d else None


def _date(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


# --------------------------------------------------------------- the data


def _supabase_rows() -> dict[str, list[dict]]:
    config = supabase.config()
    url, key = config
    res = httpx.get(
        f"{url}/auth/v1/admin/users",
        params={"page": 1, "per_page": 1000},
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=15,
    )
    res.raise_for_status()
    users = [
        {
            "id": u["id"],
            "email": u.get("email"),
            "created_at": _date(u.get("created_at")),
            "last_sign_in_at": _date(u.get("last_sign_in_at")),
        }
        for u in res.json().get("users", [])
    ]

    def table(name: str, columns: str) -> list[dict]:
        with _rest(config) as client:
            res = client.get(f"/{name}", params={"select": columns})
        res.raise_for_status()
        return res.json()

    generations = [
        {**g, "created_at": _date(g["created_at"])}
        for g in table("generations", "user_id,model,created_at")
    ]
    return {
        "users": users,
        "generations": generations,
        "sites": table("projects", "user_id"),
        "published": table("published_sites", "user_id"),
        "photos": table("site_photos", "user_id"),
    }


def _local_rows() -> dict[str, list[dict]]:
    """Plain local mode has one user and JSON files."""
    return {
        "users": [{"id": LOCAL_USER, "email": LOCAL_USER, "created_at": None}],
        "generations": [
            {"user_id": r["owner"], "model": r["model"], "created_at": _date(r["at"])}
            for r in usage._read()
        ],
        "sites": [{"user_id": LOCAL_USER} for _ in projects.list_projects(LOCAL_USER)],
        "published": [{"user_id": p["owner"]} for p in publishing._read().values()],
        "photos": [{"user_id": r["owner"]} for r in user_photos._read()],
    }
