"""Vimshopaka Bala — planetary strength across divisional charts.

Measures how well a planet is placed across multiple vargas.
Score range: 0-20 for each varga group.
Reference: BPHS Ch. 16.
"""

from ..models import Chart, VargaChart, VimshopakaBala
from .constants import RASHIS
from .strength import (
    EXALTATION, DEBILITATION, MOOLTRIKONA, OWN_SIGNS,
    FRIENDS, ENEMIES, RASHI_LORDS,
)
from .vargas import calculate_all_vargas


# Dignity score in virupas for Vimshopaka (BPHS scale)
_DIGNITY_SCORES = {
    "Exalted": 20,
    "Mooltrikona": 18,
    "Own Sign": 15,
    "Friendly": 10,
    "Neutral": 7,
    "Enemy": 5,
    "Debilitated": 2,
}

# Varga group weights (must sum to 20 for each group)
_SHAD_VARGA_WEIGHTS = {1: 6, 2: 2, 3: 4, 9: 5, 12: 2, 30: 1}  # sum=20
_SAPTA_VARGA_WEIGHTS = {1: 5, 2: 2, 3: 3, 7: 2.5, 9: 4.5, 12: 2, 30: 1}  # sum=20
_DASHA_VARGA_WEIGHTS = {
    1: 3, 2: 1.5, 3: 1.5, 7: 1.5, 9: 3,
    10: 1.5, 12: 1.5, 16: 1.5, 30: 1.5, 60: 3,
}  # sum=20
_SHODASHA_VARGA_WEIGHTS = {
    1: 3.5, 2: 1, 3: 1, 4: 0.5, 5: 0.5, 7: 1, 9: 3,
    10: 1.5, 12: 1, 16: 1, 20: 0.5, 24: 0.5, 27: 0.5,
    30: 1, 40: 0.5, 60: 3,
}  # sum=20


def _varga_dignity(planet_name: str, varga_rashi: str) -> str:
    """Determine dignity of a planet in a varga rashi (simplified)."""
    if planet_name in ("Rahu", "Ketu", "Lagna"):
        if planet_name in EXALTATION and EXALTATION[planet_name][0] == varga_rashi:
            return "Exalted"
        if planet_name in DEBILITATION and DEBILITATION[planet_name][0] == varga_rashi:
            return "Debilitated"
        return "Neutral"

    # Exaltation check (sign only, ignore degree in vargas)
    if planet_name in EXALTATION and EXALTATION[planet_name][0] == varga_rashi:
        return "Exalted"

    # Debilitation
    if planet_name in DEBILITATION and DEBILITATION[planet_name][0] == varga_rashi:
        return "Debilitated"

    # Mooltrikona (sign only for vargas)
    if planet_name in MOOLTRIKONA and MOOLTRIKONA[planet_name][0] == varga_rashi:
        return "Mooltrikona"

    # Own sign
    if planet_name in OWN_SIGNS and varga_rashi in OWN_SIGNS[planet_name]:
        return "Own Sign"

    # Relationship with rashi lord
    rashi_lord = RASHI_LORDS.get(varga_rashi, "")
    if rashi_lord == planet_name:
        return "Own Sign"
    if planet_name in FRIENDS and rashi_lord in FRIENDS[planet_name]:
        return "Friendly"
    if planet_name in ENEMIES and rashi_lord in ENEMIES[planet_name]:
        return "Enemy"
    return "Neutral"


def _weighted_score(planet_name: str, vargas: dict[int, VargaChart],
                    weights: dict[int, float]) -> float:
    """Calculate weighted vimshopaka score for a varga group."""
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0

    score = 0.0
    for div, weight in weights.items():
        varga = vargas.get(div)
        if not varga:
            continue
        # Find this planet in the varga
        for pos in varga.positions:
            if pos.name == planet_name:
                dignity = _varga_dignity(planet_name, pos.rashi)
                dignity_score = _DIGNITY_SCORES.get(dignity, 7)
                score += (dignity_score / 20) * weight
                break

    return round(score, 2)


def calculate_vimshopaka(chart: Chart,
                         vargas: dict[int, VargaChart] | None = None
                         ) -> dict[str, VimshopakaBala]:
    """Calculate Vimshopaka Bala for all planets.

    Args:
        chart: Natal chart.
        vargas: Pre-calculated varga charts (optional, computed if not given).

    Returns:
        Dict of planet_name -> VimshopakaBala.
    """
    if vargas is None:
        vargas = calculate_all_vargas(chart)

    results = {}
    planet_names = [p.name for p in chart.planets]

    for name in planet_names:
        if name in ("Rahu", "Ketu"):
            # Simplified for shadow planets
            results[name] = VimshopakaBala(planet=name)
            continue

        results[name] = VimshopakaBala(
            planet=name,
            shad_varga=_weighted_score(name, vargas, _SHAD_VARGA_WEIGHTS),
            sapta_varga=_weighted_score(name, vargas, _SAPTA_VARGA_WEIGHTS),
            dasha_varga=_weighted_score(name, vargas, _DASHA_VARGA_WEIGHTS),
            shodasha_varga=_weighted_score(name, vargas, _SHODASHA_VARGA_WEIGHTS),
        )

    return results
