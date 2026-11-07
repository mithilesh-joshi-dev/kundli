"""PDF chart download endpoint — accepts HTML form submissions."""

import asyncio
import unicodedata
from functools import partial

from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from ...config import settings
from ..api.common import BirthInput, parse_birth
from ..pdf import generate_micro_mr_pdf, generate_micro_pdf, generate_mini_mr_pdf

router = APIRouter()


@router.post("/api/pdf/chart")
async def pdf_chart_form(
    request: Request,
    name: str = Form(default=""),
    date: str = Form(...),
    time: str = Form(...),
    place: str = Form(default=""),
    lat: str = Form(default=""),
    lon: str = Form(default=""),
    utc_offset: float = Form(default=5.5),
    lang: str = Form(default=settings.app.default_lang),
    report_type: str = Form(default="micro"),
    gender: str = Form(default=""),
    gotra: str = Form(default=""),
    parents: str = Form(default=""),
):
    body = BirthInput(
        name=name or None,
        date=date,
        time=time,
        place=place or None,
        lat=float(lat) if lat else None,
        lon=float(lon) if lon else None,
        utc_offset=utc_offset,
        lang=lang,
    )
    birth = parse_birth(body)

    # Pull astrologer info from the session user's profile
    profile = getattr(request.state, "profile", None)
    astrologer_name = profile.get("display_name", "") if profile else ""
    astrologer_cred = profile.get("credentials", "") if profile else ""

    kwargs = dict(
        person_name=body.name or None,
        place_name=body.place or None,
        gender=gender or None,
        gotra=gotra or None,
        parents=parents or None,
        astrologer_name=astrologer_name or None,
        astrologer_credentials=astrologer_cred or None,
    )

    # Feature gate
    from ..auth import ALL_FEATURES
    user_features = getattr(request.state, "user_features", None) or set(ALL_FEATURES)
    feature_key = f"pdf_{report_type}"
    if feature_key not in user_features:
        from fastapi import HTTPException
        raise HTTPException(403, "या पत्रिकेसाठी परवानगी नाही. कृपया प्रशासकाशी संपर्क साधा.")

    # Build the synchronous generator callable, then run it off the event loop.
    # write_pdf() is CPU-bound (Pango text shaping + layout); keeping it on the
    # event loop would stall all other requests during generation.
    loop = asyncio.get_running_loop()
    if report_type == "micro":
        fn = (partial(generate_micro_mr_pdf, birth, **kwargs) if lang == "mr"
              else partial(generate_micro_pdf, birth, person_name=body.name or None, place_name=body.place or None))
    elif report_type == "mini":
        fn = (partial(generate_mini_mr_pdf, birth, **kwargs) if lang == "mr"
              else partial(generate_micro_pdf, birth, person_name=body.name or None, place_name=body.place or None))
    elif report_type == "full":
        from fastapi import HTTPException
        raise HTTPException(400, "Full Janma Patrika लवकरच उपलब्ध होईल.")
    else:
        from fastapi import HTTPException
        raise HTTPException(400, f"Report type '{report_type}' not yet available.")

    pdf_bytes = await loop.run_in_executor(None, fn)

    raw = body.name or "chart"
    ascii_name = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode() or "chart"
    safe_name = ascii_name.strip().replace(" ", "_") or "kundli"
    filename = f"kundli_{report_type}_{safe_name}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
