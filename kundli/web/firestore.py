"""Fire-and-forget Firestore storage for kundli requests."""

import asyncio
import logging
from typing import Any

from ..config import settings

logger = logging.getLogger("kundli.firestore")

_client = None


def _get_client():
    global _client
    if _client is None:
        from google.cloud.firestore_v1 import AsyncClient
        _client = AsyncClient()
    return _client


async def _store(doc: dict[str, Any]) -> None:
    """Write a document to Firestore. Swallows all errors."""
    try:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP
        doc["created_at"] = SERVER_TIMESTAMP
        client = _get_client()
        await client.collection(settings.firestore.collection).add(doc)
        logger.debug("Stored %s request for %s", doc.get("type"), doc.get("name"))
    except Exception:
        logger.exception("Failed to store request in Firestore")


def store_request(doc: dict[str, Any]) -> None:
    """Schedule Firestore write without blocking the response.

    No-op if Firestore is disabled.
    """
    if not settings.firestore.enabled:
        return
    asyncio.ensure_future(_store(doc))
