"""Planetary transit (Gochar) calculations."""

from datetime import datetime, timedelta, timezone

import swisseph as swe

from .constants import AYANAMSHA, RASHIS


TRANSIT_PLANETS = {
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
    "Mars": swe.MARS,
    "Venus": swe.VENUS,
    "Mercury": swe.MERCURY,
    "Sun": swe.SUN,
}


def _get_sidereal_lon(jd: float, planet_id: int) -> float:
    result, _ = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return result[0]


def calculate_transits(
    lagna_rashi_idx: int,
    moon_rashi_idx: int,
    start_year: int,
    end_year: int,
    planets: list[str] | None = None,
) -> dict[str, list[tuple[str, str, int, int, str]]]:
    """Calculate transit sign changes for planets.

    Returns dict of planet_name -> list of (start_date, rashi, house_from_lagna, house_from_moon, end_date).
    """
    swe.set_ephe_path(None)
    swe.set_sid_mode(AYANAMSHA)

    if planets is None:
        planets = ["Jupiter", "Saturn", "Rahu", "Ketu", "Mars"]

    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)

    result = {}

    for planet_name in planets:
        is_ketu = planet_name == "Ketu"
        planet_id = TRANSIT_PLANETS.get(planet_name, swe.MEAN_NODE)

        entries = []
        prev_rashi = None
        day = start

        while day <= end:
            utc_hour = 12 - 5.5  # noon IST
            jd = swe.julday(day.year, day.month, day.day, utc_hour)

            if is_ketu:
                lon = (_get_sidereal_lon(jd, swe.MEAN_NODE) + 180) % 360
            else:
                lon = _get_sidereal_lon(jd, planet_id)

            rashi_idx = int(lon / 30) % 12
            rashi = RASHIS[rashi_idx]

            if rashi != prev_rashi:
                h_lagna = ((rashi_idx - lagna_rashi_idx) % 12) + 1
                h_moon = ((rashi_idx - moon_rashi_idx) % 12) + 1
                entries.append((day.strftime("%Y-%m-%d"), rashi, h_lagna, h_moon, ""))
                # Set end date for previous entry
                if len(entries) > 1:
                    entries[-2] = (*entries[-2][:4], day.strftime("%Y-%m-%d"))
                prev_rashi = rashi

            # Step size: slow planets daily is fine, but we can optimize
            if planet_name in ("Jupiter", "Saturn", "Rahu", "Ketu"):
                day += timedelta(days=1)
            else:
                day += timedelta(days=1)

        # Set end date for last entry
        if entries:
            entries[-1] = (*entries[-1][:4], end.strftime("%Y-%m-%d"))

        result[planet_name] = entries

    swe.close()
    return result
