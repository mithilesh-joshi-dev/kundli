"""PDF chart download endpoint — accepts HTML form submissions."""

from fastapi import APIRouter, Form
from fastapi.responses import Response

from ...config import settings
from ..api.common import BirthInput, parse_birth
from ..pdf import generate_micro_mr_pdf, generate_micro_pdf

router = APIRouter()


@router.post("/api/pdf/chart")
async def pdf_chart_form(
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

    if report_type == "micro":
        if lang == "mr":
            pdf_bytes = generate_micro_mr_pdf(
                birth,
                person_name=body.name or None,
                place_name=body.place or None,
                gender=gender or None,
                gotra=gotra or None,
                parents=parents or None,
            )
        else:
            pdf_bytes = generate_micro_pdf(
                birth,
                person_name=body.name or None,
                place_name=body.place or None,
            )
    else:
        from fastapi import HTTPException
        raise HTTPException(400, f"Report type '{report_type}' not yet available.")

    import unicodedata
    raw = body.name or "chart"
    ascii_name = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode() or "chart"
    safe_name = ascii_name.strip().replace(" ", "_") or "kundli"
    filename = f"kundli_{report_type}_{safe_name}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
