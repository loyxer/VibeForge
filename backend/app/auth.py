"""Who is making the request.

With SUPABASE_URL + SUPABASE_SECRET_KEY set, every API call must carry the
Supabase session token of a signed-in user (Google or email sign-in),
and projects are scoped to that user. Without them (plain local dev) auth
is off and everything belongs to a single "local" user.
"""
import httpx
from fastapi import Header, HTTPException

from app import supabase

LOCAL_USER = "local"


def is_owner(user: str) -> bool:
    """The owner's own accounts (UNLIMITED_USER_IDS), or the single user of
    plain local mode: they have no daily limit and can see the stats."""
    from app import usage  # usage doesn't import auth, but keep it lazy anyway

    return user == LOCAL_USER or user in usage.UNLIMITED


async def current_user(authorization: str | None = Header(default=None)) -> str:
    config = supabase.config()
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


def delete_account(user_id: str) -> None:
    """Remove the user from Supabase Auth. Their projects, versions,
    published sites and usage rows go with them (on delete cascade)."""
    config = supabase.config()
    if config is None:
        return
    url, key = config
    res = httpx.delete(
        f"{url}/auth/v1/admin/users/{user_id}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=15,
    )
    if res.status_code not in (200, 204, 404):
        res.raise_for_status()
