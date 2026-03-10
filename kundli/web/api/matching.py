"""Matching API endpoint."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...calc.engine import calculate_chart
from ...calc.matching import calculate_matching
from ...config import settings
from ..i18n import get_translator
from .common import BirthInput, parse_birth

router = APIRouter()


class MatchInput(BaseModel):
    bride: BirthInput
    groom: BirthInput
    lang: str = settings.app.default_lang


@router.post("/matching")
def api_matching(body: MatchInput):
    T = get_translator(body.lang)
    bride_birth = parse_birth(body.bride)
    groom_birth = parse_birth(body.groom)

    bride_chart = calculate_chart(bride_birth)
    groom_chart = calculate_chart(groom_birth)

    results = calculate_matching(bride_chart, groom_chart)

    kootas = []
    total = 0.0
    max_total = 0.0
    for koota, score, max_score, desc in results:
        total += score
        max_total += max_score
        kootas.append({
            "name": koota,
            "score": score,
            "max_score": max_score,
            "description": desc,
        })

    pct = (total / max_total) * 100 if max_total else 0

    bride_moon = next((p.rashi for p in bride_chart.planets if p.name == "Moon"), "Unknown")
    groom_moon = next((p.rashi for p in groom_chart.planets if p.name == "Moon"), "Unknown")

    return {
        "lang": body.lang,
        "bride_moon": bride_moon,
        "groom_moon": groom_moon,
        "kootas": kootas,
        "total": total,
        "max_total": max_total,
        "percentage": round(pct, 1),
    }
