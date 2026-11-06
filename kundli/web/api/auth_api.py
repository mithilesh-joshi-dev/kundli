"""Auth endpoints — Google sign-in session management."""

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from ..auth import create_session_cookie, get_or_create_profile, revoke_tokens

logger = logging.getLogger("kundli.auth")
router = APIRouter()

_SESSION_COOKIE = "__session"
_COOKIE_MAX_AGE = 14 * 24 * 60 * 60  # 14 days in seconds


@router.post("/auth/session")
async def login(request: Request, id_token: str = Form(...)):
    """Exchange a Firebase ID token for a server-side session cookie."""
    try:
        session_cookie = create_session_cookie(id_token)
    except Exception as e:
        logger.warning("Failed to create session cookie: %s", e)
        return JSONResponse({"error": "invalid_token"}, status_code=401)

    # Decode token to get user info (already verified inside create_session_cookie)
    from firebase_admin import auth
    decoded = auth.verify_id_token(id_token)
    uid   = decoded["uid"]
    email = decoded.get("email", "")
    name  = decoded.get("name", email)

    profile = await get_or_create_profile(uid, email, name)

    response = JSONResponse({
        "ok": True,
        "approved": profile.get("approved", False),
    })
    response.set_cookie(
        _SESSION_COOKIE,
        session_cookie,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.get("/auth/logout")
async def logout(request: Request):
    # Revoke Firebase refresh tokens so the session cookie can't be reused
    user = getattr(request.state, "user", None)
    if user:
        try:
            revoke_tokens(user["uid"])
        except Exception:
            pass

    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(_SESSION_COOKIE)
    return response
