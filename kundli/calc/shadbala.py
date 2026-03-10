"""Shadbala — six-fold planetary strength (BPHS Ch. 27).

Calculates comprehensive strength for each planet:
1. Sthana Bala (positional) — dignity, house, varga placement
2. Dig Bala (directional) — planet's directional strength
3. Kala Bala (temporal) — day/night, paksha, hora
4. Cheshta Bala (motional) — speed/retrograde
5. Naisargika Bala (natural) — fixed hierarchy
6. Drig Bala (aspectual) — benefic/malefic aspects
"""

import math

from ..models import BirthData, Chart, PlanetPosition, ShadbalaResult, VargaChart
from .aspects import get_house_aspects
from .constants import (
    DIG_BALA_HOUSES, MEAN_DAILY_MOTION, NAISARGIKA_BALA,
    RASHIS, SHADBALA_REQUIRED,
)
from .strength import EXALTATION, DEBILITATION, get_dignity

# Seven main planets for Shadbala (not Rahu/Ketu)
_SHADBALA_PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")

# Natural benefics and malefics
_BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}
_MALEFICS = {"Sun", "Mars", "Saturn"}


# ===== 1. Sthana Bala (positional strength) =====

def _uchcha_bala(planet: PlanetPosition) -> float:
    """Uchcha Bala — strength from proximity to exaltation point.

    Max 60 virupas at exact exaltation degree, 0 at exact debilitation.
    """
    name = planet.name
    if name not in EXALTATION:
        return 30.0  # neutral

    exalt_rashi, exalt_deg = EXALTATION[name]
    exalt_rashi_idx = RASHIS.index(exalt_rashi)
    exalt_lon = exalt_rashi_idx * 30 + exalt_deg

    # Distance from exaltation point
    diff = abs(planet.longitude - exalt_lon)
    if diff > 180:
        diff = 360 - diff

    # 0° from exaltation = 60, 180° = 0
    return max(0, 60 * (1 - diff / 180))


def _kendra_bala(planet: PlanetPosition) -> float:
    """Bonus for kendra/trikona/upachaya placement."""
    if planet.house in {1, 4, 7, 10}:
        return 60.0   # Kendra
    elif planet.house in {5, 9}:
        return 45.0   # Trikona
    elif planet.house in {3, 6, 11}:
        return 30.0   # Upachaya
    elif planet.house in {2}:
        return 15.0
    else:
        return 0.0    # Trik houses (6,8,12)


def _sthana_bala(planet: PlanetPosition,
                 vimshopaka_score: float = 10.0) -> float:
    """Total Sthana Bala in virupas.

    Components: Uchcha + Kendra + Vimshopaka-derived.
    """
    uchcha = _uchcha_bala(planet)
    kendra = _kendra_bala(planet)
    # Vimshopaka contributes (scaled to ~60 virupas)
    vimshopaka_contrib = vimshopaka_score * 3.0  # 0-20 → 0-60

    return uchcha + kendra + vimshopaka_contrib


# ===== 2. Dig Bala (directional strength) =====

def _dig_bala(planet: PlanetPosition) -> float:
    """Directional strength. Max 60 virupas in strongest house, 0 opposite."""
    name = planet.name
    if name not in DIG_BALA_HOUSES:
        return 30.0

    strong_house = DIG_BALA_HOUSES[name]
    # House distance (minimum arc)
    dist = abs(planet.house - strong_house)
    if dist > 6:
        dist = 12 - dist

    return max(0, 60 * (1 - dist / 6))


# ===== 3. Kala Bala (temporal strength) =====

def _kala_bala(planet: PlanetPosition, birth: BirthData) -> float:
    """Temporal strength.

    Simplified: day-born benefics strong, night-born malefics strong.
    Plus paksha bala for Moon.
    """
    name = planet.name
    score = 30.0  # Base

    # Approximate day/night: 6-18 = day
    local_hour = birth.hour + birth.minute / 60
    is_day = 6 <= local_hour < 18

    if name in _BENEFICS:
        score += 15 if is_day else 0
    elif name in _MALEFICS:
        score += 15 if not is_day else 0

    # Paksha Bala for Moon — stronger when waxing (bright half)
    if name == "Moon":
        # Moon's speed > 0 and ahead of Sun = waxing
        moon_lon = planet.longitude
        # Simple: Moon > 180° from Sun = waning, < 180° = waxing
        # We don't have Sun's exact position here, use Moon's phase from rashi
        # Better: use Moon's brightness (rashi degree as proxy)
        score += 15  # Simplified, can be refined with Sun position

    return min(60, score)


# ===== 4. Cheshta Bala (motional strength) =====

def _cheshta_bala(planet: PlanetPosition) -> float:
    """Motional strength based on speed.

    Retrograde / stationary = high cheshta bala.
    Fast direct motion = lower.
    """
    name = planet.name
    if name not in MEAN_DAILY_MOTION:
        return 30.0

    if name in ("Sun", "Moon"):
        # Sun/Moon never retrograde, use fixed moderate value
        return 30.0

    mean = MEAN_DAILY_MOTION[name]
    speed = abs(planet.speed)

    if planet.is_retrograde:
        return 60.0  # Maximum — retrograde = strong cheshta

    if speed < 0.01:
        return 55.0  # Near-stationary

    # Ratio of actual to mean speed
    ratio = speed / mean if mean > 0 else 1.0

    if ratio < 0.5:
        return 45.0  # Very slow = strong
    elif ratio < 1.0:
        return 30.0  # Below average
    elif ratio < 1.5:
        return 20.0  # Above average speed
    else:
        return 10.0  # Very fast = weakest cheshta


# ===== 5. Naisargika Bala (natural strength) =====

def _naisargika_bala(planet: PlanetPosition) -> float:
    """Fixed natural strength per BPHS."""
    return NAISARGIKA_BALA.get(planet.name, 30.0)


# ===== 6. Drig Bala (aspectual strength) =====

def _drig_bala(planet: PlanetPosition, house_aspects: dict[int, list[str]]) -> float:
    """Strength from aspects received.

    Benefic aspects add, malefic aspects subtract.
    """
    aspecting = house_aspects.get(planet.house, [])
    score = 0.0
    for asp in aspecting:
        if asp == planet.name:
            continue
        if asp in ("Jupiter", "Venus"):
            score += 15.0
        elif asp in ("Mercury",):
            score += 7.5
        elif asp in ("Moon",):
            score += 7.5
        elif asp in ("Mars",):
            score -= 10.0
        elif asp in ("Saturn",):
            score -= 10.0
        elif asp in ("Sun",):
            score -= 5.0
        elif asp in ("Rahu", "Ketu"):
            score -= 7.5

    return max(-30, min(60, score))


# ===== Main calculation =====

def calculate_shadbala(chart: Chart,
                       vimshopaka: dict | None = None) -> dict[str, ShadbalaResult]:
    """Calculate Shadbala for all 7 main planets.

    Args:
        chart: Natal chart.
        vimshopaka: Pre-calculated VimshopakaBala dict (optional).

    Returns:
        Dict of planet_name -> ShadbalaResult.
    """
    house_aspects = get_house_aspects(chart)
    birth = chart.birth_data
    results = {}

    for planet in chart.planets:
        if planet.name not in _SHADBALA_PLANETS:
            continue

        vim_score = 10.0  # default
        if vimshopaka and planet.name in vimshopaka:
            vim_score = vimshopaka[planet.name].dasha_varga

        sthana = _sthana_bala(planet, vim_score)
        dig = _dig_bala(planet)
        kala = _kala_bala(planet, birth)
        cheshta = _cheshta_bala(planet)
        naisargika = _naisargika_bala(planet)
        drig = _drig_bala(planet, house_aspects)

        required = SHADBALA_REQUIRED.get(planet.name, 300)

        results[planet.name] = ShadbalaResult(
            planet=planet.name,
            sthana_bala=round(sthana, 1),
            dig_bala=round(dig, 1),
            kala_bala=round(kala, 1),
            cheshta_bala=round(cheshta, 1),
            naisargika_bala=round(naisargika, 1),
            drig_bala=round(drig, 1),
            required=required,
        )

    return results
