"""Shared API utilities — birth parsing, serialization, validation."""

import re

from fastapi import HTTPException
from pydantic import BaseModel, field_validator

from ...calc.geocode import fuzzy_search, lookup_city
from ...config import settings
from ...models import BirthData, PlanetPosition

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")


class BirthInput(BaseModel):
    name: str | None = None
    date: str
    time: str
    place: str | None = None
    lat: float | None = None
    lon: float | None = None
    utc_offset: float = settings.app.default_utc_offset
    lang: str = settings.app.default_lang

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not _DATE_RE.match(v):
            raise ValueError("Date must be YYYY-MM-DD")
        parts = v.split("-")
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        if not (settings.limits.min_year <= year <= settings.limits.max_year):
            raise ValueError(f"Year must be between {settings.limits.min_year} and {settings.limits.max_year}")
        if not (1 <= month <= 12):
            raise ValueError("Month must be 1-12")
        if not (1 <= day <= 31):
            raise ValueError("Day must be 1-31")
        return v

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        if not _TIME_RE.match(v):
            raise ValueError("Time must be HH:MM or HH:MM:SS")
        parts = v.split(":")
        if not (0 <= int(parts[0]) <= 23):
            raise ValueError("Hour must be 0-23")
        if not (0 <= int(parts[1]) <= 59):
            raise ValueError("Minute must be 0-59")
        return v

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v: float | None) -> float | None:
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("lon")
    @classmethod
    def validate_lon(cls, v: float | None) -> float | None:
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        from ..i18n import SUPPORTED_LANGUAGES
        if v not in SUPPORTED_LANGUAGES:
            return settings.app.default_lang
        return v


def parse_birth(b: BirthInput) -> BirthData:
    """Parse BirthInput into BirthData, resolving place if needed."""
    lat, lon, utc_offset = b.lat, b.lon, b.utc_offset

    if b.place and lat is None and lon is None:
        result = lookup_city(b.place)
        if result:
            lat, lon, utc_offset = result
        else:
            matches = fuzzy_search(b.place)
            if matches:
                suggestions = [f"{name} ({lt:.4f}N, {ln:.4f}E)" for name, lt, ln in matches]
                raise HTTPException(400, f"City not found. Did you mean: {', '.join(suggestions)}")
            raise HTTPException(400, f"City '{b.place}' not found. Use lat/lon instead.")

    if lat is None or lon is None:
        raise HTTPException(400, "Provide place or both lat and lon.")

    parts = b.date.split("-")
    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])

    tparts = b.time.split(":")
    hour, minute = int(tparts[0]), int(tparts[1])
    second = int(tparts[2]) if len(tparts) > 2 else 0

    return BirthData(
        year=year, month=month, day=day,
        hour=hour, minute=minute, second=second,
        latitude=lat, longitude=lon,
        utc_offset=utc_offset,
    )


def serialize_planet(p: PlanetPosition, T) -> dict:
    """Serialize a PlanetPosition with translated fields."""
    from ...calc.constants import NAKSHATRAS, NAKSHATRA_LORDS
    from ...calc.strength import get_dignity
    from ...calc.utils import dms_str

    nak_idx = NAKSHATRAS.index(p.nakshatra)
    nak_lord = NAKSHATRA_LORDS[nak_idx]
    dignity = get_dignity(p)

    return {
        "name": p.name,
        "name_local": T(f"planet.{p.name}"),
        "rashi": p.rashi,
        "rashi_local": T(f"rashi.{p.rashi}"),
        "rashi_degree": dms_str(p.rashi_degree),
        "longitude": dms_str(p.longitude),
        "nakshatra": p.nakshatra,
        "nakshatra_local": T(f"nakshatra.{p.nakshatra}"),
        "nakshatra_pada": p.nakshatra_pada,
        "nakshatra_lord": nak_lord,
        "house": p.house,
        "is_retrograde": p.is_retrograde,
        "dignity": dignity or "",
        "dignity_local": T(f"dignity.{dignity}") if dignity else "",
    }
