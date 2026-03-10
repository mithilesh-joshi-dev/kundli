"""Predict API endpoint."""

from fastapi import APIRouter
from pydantic import field_validator

from ...calc.engine import calculate_chart
from ...calc.predict import generate_predictions
from ...config import settings
from ..i18n import get_translator
from .common import BirthInput, parse_birth, serialize_planet

router = APIRouter()


class PredictInput(BirthInput):
    start_year: int = 2025
    end_year: int = 2027

    @field_validator("start_year", "end_year")
    @classmethod
    def validate_years(cls, v: int) -> int:
        if not (settings.limits.min_year <= v <= settings.limits.max_year):
            raise ValueError(f"Year must be between {settings.limits.min_year} and {settings.limits.max_year}")
        return v


@router.post("/predict")
def api_predict(body: PredictInput):
    if body.end_year - body.start_year > settings.limits.max_year_range:
        from fastapi import HTTPException
        raise HTTPException(400, f"Year range cannot exceed {settings.limits.max_year_range} years")

    T = get_translator(body.lang)
    birth = parse_birth(body)
    chart = calculate_chart(birth)
    predictions, bav, sav = generate_predictions(chart, body.start_year, body.end_year)

    from ...calc.constants import RASHIS

    bav_data = {}
    for planet, bindus in bav.items():
        bav_data[planet] = {
            "planet_local": T(f"planet.{planet}"),
            "bindus": bindus,
            "total": sum(bindus),
        }

    sav_data = {
        "values": sav,
        "rashis": [{"name": r, "name_local": T(f"rashi.{r}")} for r in RASHIS],
        "total": sum(sav),
    }

    pred_data = []
    for pred in predictions:
        # Flatten life_areas for API/template consumption
        life_areas_flat = {}
        for area_name, area_info in pred["life_areas"].items():
            if isinstance(area_info, dict):
                life_areas_flat[area_name] = {
                    "outlook": area_info.get("outlook", "mixed"),
                    "details": area_info.get("details", ""),
                    "score": area_info.get("score", 0),
                    "houses": area_info.get("houses", []),
                }
            else:
                life_areas_flat[area_name] = {"outlook": "mixed", "details": str(area_info)}

        pred_data.append({
            "period": pred["period"],
            "dasha": pred["dasha"],
            "outlook": pred["outlook"],
            "outlook_local": T(f"outlook.{pred['outlook']}"),
            "score": pred["score"],
            "analysis": pred["analysis"],
            "life_areas": life_areas_flat,
            "yogas_active": pred.get("yogas_active", []),
            "sade_sati": pred.get("sade_sati"),
            "bhrigu_bindu": pred.get("bhrigu_bindu"),
            "jupiter_cycle": pred.get("jupiter_cycle"),
            "saturn_cycle": pred.get("saturn_cycle"),
            "varga_insights": pred.get("varga_insights", {}),
        })

    moon = next((p for p in chart.planets if p.name == "Moon"), None)
    if not moon:
        from fastapi import HTTPException
        raise HTTPException(500, "Moon position could not be calculated")

    return {
        "lang": body.lang,
        "lagna": serialize_planet(chart.lagna, T),
        "moon": serialize_planet(moon, T),
        "bav": bav_data,
        "sav": sav_data,
        "predictions": pred_data,
    }
