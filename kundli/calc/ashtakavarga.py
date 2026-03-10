"""Ashtakavarga — 8-fold transit strength scoring system.

Calculates Bhinna Ashtakavarga (BAV) for each planet and
Sarvashtakavarga (SAV) totals per sign. Used to evaluate
transit strength more accurately than simple house-based rules.

Reference: Brihat Parashara Hora Shastra, Ch. 66-72.
"""

from ..models import Chart
from .constants import RASHIS

# Bindu contribution tables (house positions from each contributor).
# "Sun from Moon: [3,6,10,11]" means Sun gets a bindu when Moon is
# in the 3rd, 6th, 10th, or 11th house from Sun's position.
ASHTAKAVARGA_BINDUS = {
    "Sun": {
        "Sun":     [1, 2, 4, 7, 8, 9, 10, 11],
        "Moon":    [3, 6, 10, 11],
        "Mars":    [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [5, 6, 9, 11],
        "Venus":   [6, 7, 12],
        "Saturn":  [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna":   [3, 4, 6, 10, 11, 12],
    },  # Total: 48
    "Moon": {
        "Sun":     [3, 6, 7, 8, 10, 11],
        "Moon":    [1, 3, 6, 7, 9, 10, 11],
        "Mars":    [2, 3, 5, 6, 10, 11],
        "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "Jupiter": [1, 2, 4, 7, 8, 10, 11],
        "Venus":   [3, 4, 5, 7, 9, 10, 11],
        "Saturn":  [3, 5, 6, 11],
        "Lagna":   [3, 6, 10, 11],
    },  # Total: 49
    "Mars": {
        "Sun":     [3, 5, 6, 10, 11],
        "Moon":    [3, 6, 11],
        "Mars":    [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [3, 5, 6, 11],
        "Jupiter": [6, 10, 11, 12],
        "Venus":   [6, 8, 11, 12],
        "Saturn":  [1, 4, 7, 8, 9, 10, 11],
        "Lagna":   [1, 3, 6, 10, 11],
    },  # Total: 39
    "Mercury": {
        "Sun":     [5, 6, 9, 11, 12],
        "Moon":    [2, 4, 6, 8, 10, 11],
        "Mars":    [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [6, 8, 11, 12],
        "Venus":   [1, 2, 3, 4, 5, 8, 9, 11],
        "Saturn":  [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna":   [1, 2, 4, 6, 8, 10, 11],
    },  # Total: 54
    "Jupiter": {
        "Sun":     [1, 2, 3, 4, 7, 8, 9, 10, 11],
        "Moon":    [2, 5, 7, 9, 11],
        "Mars":    [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "Venus":   [2, 5, 6, 9, 10, 11],
        "Saturn":  [3, 5, 6, 12],
        "Lagna":   [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },  # Total: 56
    "Venus": {
        "Sun":     [8, 11, 12],
        "Moon":    [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Mars":    [3, 4, 6, 9, 11, 12],
        "Mercury": [3, 5, 6, 9, 11],
        "Jupiter": [5, 8, 9, 10, 11],
        "Venus":   [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "Saturn":  [3, 4, 5, 8, 9, 10, 11],
        "Lagna":   [1, 2, 3, 4, 5, 8, 9, 11],
    },  # Total: 52
    "Saturn": {
        "Sun":     [1, 2, 4, 7, 8, 10, 11],
        "Moon":    [3, 6, 11],
        "Mars":    [3, 5, 6, 10, 11, 12],
        "Mercury": [6, 8, 9, 10, 11, 12],
        "Jupiter": [5, 6, 11, 12],
        "Venus":   [6, 11, 12],
        "Saturn":  [3, 5, 6, 11],
        "Lagna":   [1, 3, 4, 6, 10, 11],
    },  # Total: 39
}

# Planet name -> list of 7 planets that contribute
_CONTRIBUTORS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]


def calculate_bav(chart: Chart) -> dict[str, list[int]]:
    """Calculate Bhinna Ashtakavarga for each planet.

    Returns dict of planet_name -> list of 12 bindu counts (index 0 = first rashi).
    """
    # Get rashi index (0-11) for each planet and lagna
    positions: dict[str, int] = {}
    for p in chart.planets:
        if p.name in _CONTRIBUTORS:
            positions[p.name] = int(p.longitude / 30) % 12
    positions["Lagna"] = int(chart.lagna.longitude / 30) % 12

    bav: dict[str, list[int]] = {}

    for planet in _CONTRIBUTORS:
        if planet not in ASHTAKAVARGA_BINDUS:
            continue

        bindus = [0] * 12  # one per rashi

        for contributor, houses in ASHTAKAVARGA_BINDUS[planet].items():
            if contributor not in positions:
                continue
            contrib_rashi = positions[contributor]
            for h in houses:
                # House h from contributor means rashi at (contrib_rashi + h - 1) % 12
                target_rashi = (contrib_rashi + h - 1) % 12
                bindus[target_rashi] += 1

        bav[planet] = bindus

    return bav


def calculate_sav(bav: dict[str, list[int]]) -> list[int]:
    """Calculate Sarvashtakavarga (sum of all BAV per sign).

    Returns list of 12 totals. Average is ~28 per sign (337/12).
    """
    sav = [0] * 12
    for planet_bindus in bav.values():
        for i in range(12):
            sav[i] += planet_bindus[i]
    return sav


def get_transit_score(bav: dict[str, list[int]], planet: str,
                      transit_rashi_idx: int) -> tuple[int, str]:
    """Get transit strength for a planet in a given rashi.

    Returns (bindus, quality) where quality is "strong"/"moderate"/"weak".
    """
    if planet not in bav:
        return 4, "moderate"  # default for Rahu/Ketu

    bindus = bav[planet][transit_rashi_idx]

    # Average BAV varies by planet, but roughly:
    # 4+ is good, 3 is average, 0-2 is weak
    if bindus >= 5:
        quality = "strong"
    elif bindus >= 4:
        quality = "good"
    elif bindus >= 3:
        quality = "moderate"
    elif bindus >= 2:
        quality = "weak"
    else:
        quality = "very weak"

    return bindus, quality
