"""Firebase Auth helpers — session cookie creation and verification."""

import logging
from datetime import timedelta
from typing import Any

logger = logging.getLogger("kundli.auth")

_firebase_app = None


def _app():
    global _firebase_app
    if _firebase_app is None:
        import firebase_admin
        _firebase_app = firebase_admin.initialize_app()
    return _firebase_app


def create_session_cookie(id_token: str) -> str:
    from firebase_admin import auth
    _app()
    return auth.create_session_cookie(id_token, expires_in=timedelta(days=14))


def verify_session(cookie: str) -> dict[str, Any]:
    """Verify session cookie and return decoded claims. Raises on failure."""
    from firebase_admin import auth
    _app()
    return auth.verify_session_cookie(cookie, check_revoked=True)


def revoke_tokens(uid: str) -> None:
    from firebase_admin import auth
    _app()
    auth.revoke_refresh_tokens(uid)


# ── Firestore user profile ────────────────────────────────────────────────────

async def get_or_create_profile(uid: str, email: str, name: str) -> dict[str, Any]:
    """Return the user's Firestore profile, creating a pending one if absent."""
    from google.cloud.firestore_v1 import AsyncClient, SERVER_TIMESTAMP
    client = AsyncClient()
    ref = client.collection("jyotishacharyas").document(uid)
    doc = await ref.get()
    if doc.exists:
        return doc.to_dict()

    profile = {
        "uid": uid,
        "email": email,
        "name": name,
        "display_name": name,
        "credentials": "",
        "features": [],
        "approved": False,
        "created_at": SERVER_TIMESTAMP,
    }
    await ref.set(profile)
    logger.info("Created pending profile for %s", email)
    return profile


async def get_profile(uid: str) -> dict[str, Any] | None:
    from google.cloud.firestore_v1 import AsyncClient
    client = AsyncClient()
    doc = await client.collection("jyotishacharyas").document(uid).get()
    return doc.to_dict() if doc.exists else None


async def update_profile(uid: str, display_name: str, credentials: str) -> None:
    from google.cloud.firestore_v1 import AsyncClient
    client = AsyncClient()
    await client.collection("jyotishacharyas").document(uid).update({
        "display_name": display_name,
        "credentials": credentials,
    })
