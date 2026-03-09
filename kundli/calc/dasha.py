"""Vimshottari Dasha calculations."""

from datetime import datetime, timedelta

from ..models import Chart
from .constants import NAKSHATRA_LORDS, NAKSHATRAS

# Vimshottari Dasha periods in years
DASHA_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10,
    "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19,
    "Mercury": 17,
}

# Dasha sequence
DASHA_SEQUENCE = [
    "Ketu", "Venus", "Sun", "Moon", "Mars",
    "Rahu", "Jupiter", "Saturn", "Mercury",
]

TOTAL_DASHA_YEARS = 120  # Sum of all dasha periods


def _get_moon_nakshatra(chart: Chart) -> tuple[int, float]:
    """Return (nakshatra_index, fraction_elapsed_in_nakshatra) for Moon."""
    moon = next(p for p in chart.planets if p.name == "Moon")
    lon = moon.longitude
    nak_span = 360 / 27
    nak_idx = int(lon / nak_span) % 27
    fraction = (lon % nak_span) / nak_span
    return nak_idx, fraction


def calculate_dasha(chart: Chart) -> list[tuple[str, datetime, datetime, list[tuple[str, datetime, datetime]]]]:
    """Calculate Mahadasha periods with Antardashas.

    Returns list of (planet, start_date, end_date, antardashas)
    where antardashas is list of (planet, start, end).
    """
    b = chart.birth_data
    birth_date = datetime(b.year, b.month, b.day, b.hour, b.minute, b.second)

    nak_idx, fraction_elapsed = _get_moon_nakshatra(chart)
    nak_lord = NAKSHATRA_LORDS[nak_idx]

    # Find starting dasha lord index in sequence
    start_idx = DASHA_SEQUENCE.index(nak_lord)

    # Remaining period of first dasha
    first_dasha_total_days = DASHA_YEARS[nak_lord] * 365.25
    remaining_fraction = 1 - fraction_elapsed
    first_dasha_remaining_days = first_dasha_total_days * remaining_fraction

    # Build dasha periods
    dashas = []
    current_date = birth_date

    for i in range(9):
        lord = DASHA_SEQUENCE[(start_idx + i) % 9]
        if i == 0:
            period_days = first_dasha_remaining_days
        else:
            period_days = DASHA_YEARS[lord] * 365.25

        end_date = current_date + timedelta(days=period_days)

        # Calculate Antardashas within this Mahadasha
        antardashas = _calculate_antardasha(lord, current_date, period_days, start_idx + i)

        dashas.append((lord, current_date, end_date, antardashas))
        current_date = end_date

    return dashas


def _calculate_antardasha(
    maha_lord: str,
    maha_start: datetime,
    maha_days: float,
    maha_seq_idx: int,
) -> list[tuple[str, datetime, datetime]]:
    """Calculate Antardasha periods within a Mahadasha."""
    maha_years = maha_days / 365.25
    ad_lord_idx = DASHA_SEQUENCE.index(maha_lord)
    antardashas = []
    current = maha_start

    for i in range(9):
        ad_lord = DASHA_SEQUENCE[(ad_lord_idx + i) % 9]
        # Antardasha duration = (maha_years * ad_years / total) in days
        ad_days = (maha_years * DASHA_YEARS[ad_lord] / TOTAL_DASHA_YEARS) * 365.25
        ad_end = current + timedelta(days=ad_days)
        antardashas.append((ad_lord, current, ad_end))
        current = ad_end

    return antardashas
