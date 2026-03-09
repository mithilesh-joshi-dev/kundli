"""Navamsa (D9) divisional chart calculation."""

from ..models import Chart, PlanetPosition
from .constants import RASHIS
from .utils import longitude_to_nakshatra, longitude_to_rashi


def _navamsa_rashi(longitude: float) -> tuple[int, str]:
    """Calculate Navamsa rashi for a given sidereal longitude.

    Each rashi (30°) is divided into 9 navamsas of 3°20' each.
    The navamsa rashi cycles through all 12 signs starting from:
    - Fire signs (Mesha, Simha, Dhanu): start from Mesha
    - Earth signs (Vrishabha, Kanya, Makara): start from Makara
    - Air signs (Mithuna, Tula, Kumbha): start from Tula
    - Water signs (Karka, Vrischika, Meena): start from Karka
    """
    rashi_idx = int(longitude / 30) % 12
    navamsa_in_rashi = int((longitude % 30) / (30 / 9))  # 0-8

    # Starting navamsa rashi based on element
    element_starts = {
        0: 0,   # Mesha (Fire) -> Mesha
        1: 9,   # Vrishabha (Earth) -> Makara
        2: 6,   # Mithuna (Air) -> Tula
        3: 3,   # Karka (Water) -> Karka
        4: 0,   # Simha (Fire) -> Mesha
        5: 9,   # Kanya (Earth) -> Makara
        6: 6,   # Tula (Air) -> Tula
        7: 3,   # Vrischika (Water) -> Karka
        8: 0,   # Dhanu (Fire) -> Mesha
        9: 9,   # Makara (Earth) -> Makara
        10: 6,  # Kumbha (Air) -> Tula
        11: 3,  # Meena (Water) -> Karka
    }

    start = element_starts[rashi_idx]
    nav_rashi_idx = (start + navamsa_in_rashi) % 12
    return nav_rashi_idx, RASHIS[nav_rashi_idx]


def calculate_navamsa(chart: Chart) -> list[tuple[str, str, int]]:
    """Calculate Navamsa positions for all planets and Lagna.

    Returns list of (planet_name, navamsa_rashi, navamsa_house).
    Navamsa house is relative to Navamsa Lagna.
    """
    # Lagna navamsa
    lagna_nav_idx, lagna_nav_rashi = _navamsa_rashi(chart.lagna.longitude)

    positions = [("Lagna", lagna_nav_rashi, 1)]

    for planet in chart.planets:
        nav_idx, nav_rashi = _navamsa_rashi(planet.longitude)
        house = ((nav_idx - lagna_nav_idx) % 12) + 1
        positions.append((planet.name, nav_rashi, house))

    return positions
