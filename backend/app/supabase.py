"""Connection details for the Supabase project (database + auth).

Everything here is optional: without SUPABASE_URL + SUPABASE_SECRET_KEY
the app runs in plain local mode (no accounts, JSON files on disk).
"""
import os

import httpx


def config() -> tuple[str, str] | None:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SECRET_KEY", "")
    return (url, key) if url and key else None


def rest(config: tuple[str, str]) -> httpx.Client:
    """Client for Supabase's REST API over our tables, authorised with the
    secret key (full access — only ever used on the server)."""
    url, key = config
    return httpx.Client(
        base_url=f"{url}/rest/v1",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=15,
    )
