"""Per-user daily generation limit.

Every successful generation is recorded (who, when, which model). Before
generating we count the user's records since midnight Kyiv time; once that
reaches DAILY_GENERATION_LIMIT (default 5 with accounts on, 0 = unlimited)
they have to wait for tomorrow. Failed generations are never recorded, so they don't count.

Same two backends as projects.py: a Supabase table (see
backend/supabase/schema.sql) or a local JSON file.
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app import supabase
from app.supabase import rest as _rest

# Without accounts (no Supabase) every visitor is the same "local" user, so
# a per-user limit would be one limit for the whole site — off by default.
DAILY_LIMIT = int(
    os.getenv("DAILY_GENERATION_LIMIT", "5" if supabase.config() else "0")
)
_DAY_TZ = ZoneInfo("Europe/Kyiv")


def start_of_today() -> datetime:
    now = datetime.now(_DAY_TZ)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def remaining_today(owner: str) -> int | None:
    """How many generations the user has left today; None = no limit."""
    if DAILY_LIMIT <= 0:
        return None
    return max(DAILY_LIMIT - _count_since(owner, start_of_today()), 0)


def record(owner: str, model: str) -> None:
    at = datetime.now(timezone.utc)
    if config := supabase.config():
        with _rest(config) as client:
            res = client.post(
                "/generations",
                json={"user_id": owner, "model": model, "created_at": at.isoformat()},
            )
        res.raise_for_status()
        return
    with _lock:
        rows = _read()
        rows.append({"owner": owner, "model": model, "at": at.isoformat()})
        _write(rows)


def _count_since(owner: str, since: datetime) -> int:
    if config := supabase.config():
        with _rest(config) as client:
            res = client.get(
                "/generations",
                params={
                    "user_id": f"eq.{owner}",
                    "created_at": f"gte.{since.isoformat()}",
                    "select": "id",
                },
                # Just the total, not the rows: PostgREST puts it in the
                # Content-Range header ("0-0/3" or "*/0").
                headers={"Prefer": "count=exact", "Range": "0-0"},
            )
        res.raise_for_status()
        return int(res.headers["Content-Range"].split("/")[1])
    with _lock:
        return sum(
            1
            for row in _read()
            if row["owner"] == owner and datetime.fromisoformat(row["at"]) >= since
        )


# --------------------------------------------------------------- JSON file

_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "usage.json"
_lock = threading.Lock()


def _read() -> list[dict]:
    if not _STORE_PATH.exists():
        return []
    return json.loads(_STORE_PATH.read_text())


def _write(rows: list[dict]) -> None:
    _STORE_PATH.parent.mkdir(exist_ok=True)
    _STORE_PATH.write_text(json.dumps(rows, indent=2))
