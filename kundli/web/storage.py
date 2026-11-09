"""Firebase Cloud Storage helpers — PDF upload and URL generation."""

import logging
from urllib.parse import quote

from ..config import settings

logger = logging.getLogger("kundli.storage")


def _bucket():
    from firebase_admin import storage
    from .auth import _app
    _app()
    return storage.bucket(name=settings.storage.bucket)


def _upload_sync(uid: str, record_id: str, pdf_type: str, pdf_bytes: bytes) -> str:
    path = f"kundalis/{uid}/{record_id}_{pdf_type}.pdf"
    blob = _bucket().blob(path)
    blob.upload_from_string(pdf_bytes, content_type="application/pdf")
    encoded = quote(path, safe="")
    return f"https://storage.googleapis.com/{settings.storage.bucket}/{encoded}"


def _delete_sync(uid: str, record_id: str, pdf_type: str) -> None:
    path = f"kundalis/{uid}/{record_id}_{pdf_type}.pdf"
    try:
        _bucket().blob(path).delete()
    except Exception:
        pass


async def upload_pdf(uid: str, record_id: str, pdf_type: str, pdf_bytes: bytes) -> str:
    """Upload PDF to Firebase Storage; returns permanent download URL."""
    if not settings.storage.enabled:
        return ""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _upload_sync, uid, record_id, pdf_type, pdf_bytes)
    except Exception:
        logger.exception("Failed to upload PDF uid=%s record=%s type=%s", uid, record_id, pdf_type)
        return ""


async def delete_pdf(uid: str, record_id: str, pdf_type: str) -> None:
    """Delete a PDF from storage. Swallows errors."""
    if not settings.storage.enabled:
        return
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _delete_sync, uid, record_id, pdf_type)
    except Exception:
        logger.exception("Failed to delete PDF uid=%s record=%s type=%s", uid, record_id, pdf_type)
