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


# ── Janmanav (suggested names) ────────────────────────────────────────────────

_JANMANAV_COLLECTION = "janmanav"
_janmanav_cache: dict[str, dict] | None = None  # syllable → {m, f, nakshatra, pada}


def _build_seed() -> dict[str, dict]:
    """Build seed data from Python dict + nakshatra/pada metadata."""
    from ..calc.janmanav import JANMANAV
    from ..calc.constants import NAKSHATRAS, NAKSHATRA_JANMAKSHARA
    seed = {}
    for nak_idx, syllables in enumerate(NAKSHATRA_JANMAKSHARA):
        for pada_idx, syllable in enumerate(syllables):
            names = JANMANAV.get(syllable, {"m": "—", "f": "—"})
            seed[syllable] = {
                "m": names.get("m", "—"),
                "f": names.get("f", "—"),
                "nakshatra": NAKSHATRAS[nak_idx],
                "pada": pada_idx + 1,
            }
    return seed


async def ensure_janmanav_loaded() -> None:
    """Load janmanav entries from Firestore into cache. Seeds if collection is empty."""
    global _janmanav_cache
    if _janmanav_cache is not None:
        return
    if not settings.firestore.enabled:
        _janmanav_cache = _build_seed()
        return
    try:
        client = _get_client()
        col = client.collection(_JANMANAV_COLLECTION)
        docs = [d async for d in col.stream()]
        if docs:
            _janmanav_cache = {d.id: d.to_dict() for d in docs}
            logger.info("Loaded %d janmanav entries from Firestore", len(_janmanav_cache))
        else:
            seed = _build_seed()
            batch = client.batch()
            for syllable, data in seed.items():
                batch.set(col.document(syllable), data)
            await batch.commit()
            _janmanav_cache = seed
            logger.info("Seeded %d janmanav entries to Firestore", len(seed))
    except Exception:
        logger.exception("Failed to load janmanav from Firestore; using Python dict")
        _janmanav_cache = _build_seed()


def get_janmanav_name_sync(syllable: str, gender: str) -> str:
    """Sync lookup for use in thread-pool PDF generation. Falls back to Python dict."""
    if _janmanav_cache:
        entry = _janmanav_cache.get(syllable)
        if entry:
            return entry.get(gender, "—") or "—"
    from ..calc.janmanav import JANMANAV
    return JANMANAV.get(syllable, {}).get(gender, "—") or "—"


async def get_all_janmanav() -> list[dict]:
    """Return all 108 entries sorted by nakshatra + pada for the editor UI."""
    await ensure_janmanav_loaded()
    from ..calc.constants import NAKSHATRAS, NAKSHATRA_JANMAKSHARA
    rows = []
    for nak_idx, syllables in enumerate(NAKSHATRA_JANMAKSHARA):
        for pada_idx, syllable in enumerate(syllables):
            entry = (_janmanav_cache or {}).get(syllable, {"m": "—", "f": "—"})
            rows.append({
                "syllable": syllable,
                "nakshatra": NAKSHATRAS[nak_idx],
                "pada": pada_idx + 1,
                "m": entry.get("m", "—"),
                "f": entry.get("f", "—"),
            })
    return rows


async def update_janmanav_entry(syllable: str, m: str, f: str) -> None:
    """Update a single janmanav entry in Firestore and the in-memory cache."""
    global _janmanav_cache
    await ensure_janmanav_loaded()
    data = {"m": m.strip(), "f": f.strip()}
    if settings.firestore.enabled:
        try:
            client = _get_client()
            await client.collection(_JANMANAV_COLLECTION).document(syllable).update(data)
        except Exception:
            logger.exception("Failed to update janmanav entry %s in Firestore", syllable)
            raise
    if _janmanav_cache and syllable in _janmanav_cache:
        _janmanav_cache[syllable].update(data)
