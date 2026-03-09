from datetime import datetime, timedelta, timezone

import swisseph as swe

from .constants import NAKSHATRAS, RASHIS


def longitude_to_rashi(lon: float) -> tuple[int, str, float]:
    """Convert sidereal longitude to (rashi_index, rashi_name, degrees_in_rashi)."""
    idx = int(lon / 30) % 12
    return idx, RASHIS[idx], lon % 30


def longitude_to_nakshatra(lon: float) -> tuple[int, str, int]:
    """Convert sidereal longitude to (nakshatra_index, nakshatra_name, pada)."""
    nak_span = 360 / 27  # 13.333...
    pada_span = nak_span / 4
    idx = int(lon / nak_span) % 27
    pada = int((lon % nak_span) / pada_span) + 1
    return idx, NAKSHATRAS[idx], min(pada, 4)


def to_julian_day(year: int, month: int, day: int,
                  hour: int, minute: int, second: int,
                  utc_offset: float) -> float:
    """Convert local date/time to Julian Day in UT."""
    local = datetime(year, month, day, hour, minute, second,
                     tzinfo=timezone(timedelta(hours=utc_offset)))
    utc = local.astimezone(timezone.utc)
    utc_hour = utc.hour + utc.minute / 60 + utc.second / 3600
    return swe.julday(utc.year, utc.month, utc.day, utc_hour)


def dms_str(degrees: float) -> str:
    """Format degrees as DD°MM'SS\"."""
    d = int(degrees)
    rem = (degrees - d) * 60
    m = int(rem)
    s = int((rem - m) * 60)
    return f"{d:02d}°{m:02d}'{s:02d}\""
