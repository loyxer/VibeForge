"""Who is making the request.

With SUPABASE_URL + SUPABASE_SECRET_KEY set, every API call must carry the
Supabase session token of a signed-in user (Google login on the frontend),
and projects are scoped to that user. Without them (plain local dev) auth
is off and everything belongs to a single "local" user.
"""
import os

import httpx
from fastapi import Header, HTTPException

LOCAL_USER = "local"


def supabase_config() -> tuple[str, str] | None:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SECRET_KEY", "")
    return (url, key) if url and key else None


async def current_user(authorization: str | None = Header(default=None)) -> str:
    config = supabase_config()
    if config is None:
        return LOCAL_USER

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in to continue")

    # Ask Supabase Auth itself whether the token is valid — works no matter
    # which JWT signing scheme the project uses, and costs one fast request
    # next to generations that take seconds anyway.
    url, key = config
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                f"{url}/auth/v1/user",
                headers={"apikey": key, "Authorization": authorization},
            )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Sign-in service unavailable — try again")
    if res.status_code != 200:
        raise HTTPException(status_code=401, detail="Session expired — sign in again")
    return res.json()["id"]
