"""Transit API endpoint."""

from fastapi import APIRouter, HTTPException
from pydantic import field_validator

from ...calc.engine import calculate_chart
from ...calc.transit import calculate_transits
from ...config import settings
from ..i18n import get_translator
from .common import BirthInput, parse_birth

router = APIRouter()


class TransitInput(BirthInput):
    start_year: int = 2025
    end_year: int = 2027
    planets: str | None = None

    @field_validator("start_year", "end_year")
    @classmethod
    def validate_years(cls, v: int) -> int:
        if not (settings.limits.min_year <= v <= settings.limits.max_year):
            raise ValueError(f"Year must be between {settings.limits.min_year} and {settings.limits.max_year}")
        return v


@router.post("/transit")
def api_transit(body: TransitInput):
    if body.end_year - body.start_year > settings.limits.max_year_range:
        raise HTTPException(400, f"Year range cannot exceed {settings.limits.max_year_range} years")

    T = get_translator(body.lang)
    birth = parse_birth(body)
    chart = calculate_chart(birth)

    lagna_rashi_idx = int(chart.lagna.longitude / 30) % 12
    moon = next((p for p in chart.planets if p.name == "Moon"), None)
    if not moon:
        raise HTTPException(500, "Moon position could not be calculated")
    moon_rashi_idx = int(moon.longitude / 30) % 12

    planet_list = None
    if body.planets:
        planet_list = [p.strip().title() for p in body.planets.split(",")]

    transits = calculate_transits(lagna_rashi_idx, moon_rashi_idx,
                                  body.start_year, body.end_year, planet_list)

    result = {}
    for planet_name, entries in transits.items():
        result[planet_name] = {
            "planet_local": T(f"planet.{planet_name}"),
            "entries": [
                {
                    "start": start_date,
                    "end": end_date or "...",
                    "rashi": rashi,
                    "rashi_local": T(f"rashi.{rashi}"),
                    "house_from_lagna": h_lagna,
                    "house_from_moon": h_moon,
                }
                for start_date, rashi, h_lagna, h_moon, end_date in entries
            ],
        }

    return {
        "lang": body.lang,
        "lagna_rashi": chart.lagna.rashi,
        "moon_rashi": moon.rashi,
        "transits": result,
    }
