"""Event timing API endpoint."""

from fastapi import APIRouter, HTTPException
from pydantic import field_validator

from ...calc.analysis import build_analysis
from ...calc.engine import calculate_chart
from ...calc.events2 import predict_event, EVENTS
from ...config import settings
from ..i18n import get_translator
from .common import BirthInput, parse_birth

router = APIRouter()


class EventInput(BirthInput):
    event: str = "marriage"
    start_year: int = 2025
    end_year: int = 2032

    @field_validator("event")
    @classmethod
    def validate_event(cls, v: str) -> str:
        if v not in EVENTS:
            raise ValueError(f"Unknown event. Choose from: {', '.join(EVENTS.keys())}")
        return v

    @field_validator("start_year", "end_year")
    @classmethod
    def validate_years(cls, v: int) -> int:
        if not (settings.limits.min_year <= v <= settings.limits.max_year):
            raise ValueError(f"Year must be between {settings.limits.min_year} and {settings.limits.max_year}")
        return v


@router.post("/events")
def api_events(body: EventInput):
    if body.end_year - body.start_year > settings.limits.max_year_range:
        raise HTTPException(400, f"Year range cannot exceed {settings.limits.max_year_range} years")

    T = get_translator(body.lang)
    birth = parse_birth(body)
    chart = calculate_chart(birth)
    ana = build_analysis(chart)
    result = predict_event(ana, body.event, body.start_year, body.end_year)

    return {
        "lang": body.lang,
        "event": result["event"],
        "question": result["question"],
        "houses": result["houses"],
        "karakas": result["karakas"],
        "house_details": result["house_details"],
        "natal_analysis": result["natal_analysis"],
        "bhrigu_bindu": result["bhrigu_bindu"],
        "windows": result["windows"],
        "best_period": result["best_period"],
        "total_windows": result["total_windows"],
        "available_events": {k: v.question for k, v in EVENTS.items()},
    }
