"""Ashtakoot Milan (8-fold marriage compatibility matching)."""

from ..models import Chart
from .constants import NAKSHATRAS, RASHIS
from .nakshatra_attrs import (
    BHAKOOT_BAD_PAIRS,
    NAKSHATRA_GANA,
    NAKSHATRA_NADI,
    NAKSHATRA_VARNA,
    NAKSHATRA_YONI,
    RASHI_VASHYA,
    YONI_ENEMIES,
    get_nakshatra_attrs,
)
from .strength import RASHI_LORDS
from .utils import longitude_to_nakshatra, longitude_to_rashi


def _get_moon_info(chart: Chart) -> tuple[int, int, str]:
    """Return (nakshatra_index, rashi_index, rashi_name) for Moon."""
    moon = next(p for p in chart.planets if p.name == "Moon")
    nak_idx = NAKSHATRAS.index(moon.nakshatra)
    rashi_idx = int(moon.longitude / 30) % 12
    return nak_idx, rashi_idx, moon.rashi


def calculate_matching(bride_chart: Chart, groom_chart: Chart) -> list[tuple[str, float, float, str]]:
    """Calculate Ashtakoot Milan between two charts.

    Returns list of (koota_name, score, max_score, description).
    """
    b_nak, b_rashi_idx, b_rashi = _get_moon_info(bride_chart)
    g_nak, g_rashi_idx, g_rashi = _get_moon_info(groom_chart)

    results = []

    # 1. Varna (1 point) — Groom's varna should be >= Bride's
    varna_order = {"Brahmin": 4, "Kshatriya": 3, "Vaishya": 2, "Shudra": 1}
    b_varna = NAKSHATRA_VARNA[b_nak]
    g_varna = NAKSHATRA_VARNA[g_nak]
    varna_score = 1.0 if varna_order[g_varna] >= varna_order[b_varna] else 0.0
    results.append(("Varna", varna_score, 1.0,
                    f"Groom: {g_varna}, Bride: {b_varna}"))

    # 2. Vashya (2 points)
    b_vashya = RASHI_VASHYA[b_rashi]
    g_vashya = RASHI_VASHYA[g_rashi]
    if b_vashya == g_vashya:
        vashya_score = 2.0
    elif _is_vashya_compatible(g_vashya, b_vashya):
        vashya_score = 1.0
    else:
        vashya_score = 0.0
    results.append(("Vashya", vashya_score, 2.0,
                    f"Groom: {g_vashya} ({g_rashi}), Bride: {b_vashya} ({b_rashi})"))

    # 3. Tara (3 points) — Based on birth star distance
    tara_dist = (g_nak - b_nak) % 27
    tara_remainder = (tara_dist % 9) + 1
    # Favorable taras: 1(Janma), 2(Sampat), 4(Kshema), 6(Sadhana), 8(Mitra), 9(Parama Mitra)
    favorable_taras = {1, 2, 4, 6, 8, 9}
    # Also check reverse
    tara_dist_rev = (b_nak - g_nak) % 27
    tara_rem_rev = (tara_dist_rev % 9) + 1
    if tara_remainder in favorable_taras and tara_rem_rev in favorable_taras:
        tara_score = 3.0
    elif tara_remainder in favorable_taras or tara_rem_rev in favorable_taras:
        tara_score = 1.5
    else:
        tara_score = 0.0
    tara_names = {1: "Janma", 2: "Sampat", 3: "Vipat", 4: "Kshema",
                  5: "Pratyari", 6: "Sadhana", 7: "Vadha", 8: "Mitra", 9: "Parama Mitra"}
    results.append(("Tara", tara_score, 3.0,
                    f"Forward: {tara_names.get(tara_remainder, '?')}, "
                    f"Reverse: {tara_names.get(tara_rem_rev, '?')}"))

    # 4. Yoni (4 points)
    b_animal, b_gender = NAKSHATRA_YONI[b_nak]
    g_animal, g_gender = NAKSHATRA_YONI[g_nak]
    if b_animal == g_animal:
        if b_gender != g_gender:
            yoni_score = 4.0  # Same animal, opposite gender — best
        else:
            yoni_score = 3.0  # Same animal, same gender
    elif YONI_ENEMIES.get(b_animal) == g_animal:
        yoni_score = 0.0  # Enemy animals
    elif b_gender != g_gender:
        yoni_score = 2.0  # Different animals, opposite gender
    else:
        yoni_score = 1.0  # Different animals, same gender
    results.append(("Yoni", yoni_score, 4.0,
                    f"Groom: {g_animal} ({g_gender}), Bride: {b_animal} ({b_gender})"))

    # 5. Graha Maitri (5 points) — Rashi lord friendship
    b_lord = RASHI_LORDS[b_rashi]
    g_lord = RASHI_LORDS[g_rashi]
    maitri_score = _graha_maitri_score(g_lord, b_lord)
    results.append(("Graha Maitri", maitri_score, 5.0,
                    f"Groom lord: {g_lord} ({g_rashi}), Bride lord: {b_lord} ({b_rashi})"))

    # 6. Gana (6 points)
    b_gana = NAKSHATRA_GANA[b_nak]
    g_gana = NAKSHATRA_GANA[g_nak]
    if b_gana == g_gana:
        gana_score = 6.0
    elif {b_gana, g_gana} == {"Deva", "Manushya"}:
        gana_score = 3.0
    elif {b_gana, g_gana} == {"Manushya", "Rakshasa"}:
        gana_score = 1.0
    else:  # Deva-Rakshasa
        gana_score = 0.0
    results.append(("Gana", gana_score, 6.0,
                    f"Groom: {g_gana}, Bride: {b_gana}"))

    # 7. Bhakoot (7 points)
    dist_g_to_b = ((b_rashi_idx - g_rashi_idx) % 12) + 1
    dist_b_to_g = ((g_rashi_idx - b_rashi_idx) % 12) + 1
    if (dist_g_to_b, dist_b_to_g) in BHAKOOT_BAD_PAIRS:
        bhakoot_score = 0.0
        bhakoot_desc = f"Distance: {dist_g_to_b}-{dist_b_to_g} (inauspicious)"
    else:
        bhakoot_score = 7.0
        bhakoot_desc = f"Distance: {dist_g_to_b}-{dist_b_to_g} (auspicious)"
    results.append(("Bhakoot", bhakoot_score, 7.0, bhakoot_desc))

    # 8. Nadi (8 points) — Must be different
    b_nadi = NAKSHATRA_NADI[b_nak]
    g_nadi = NAKSHATRA_NADI[g_nak]
    nadi_score = 8.0 if b_nadi != g_nadi else 0.0
    results.append(("Nadi", nadi_score, 8.0,
                    f"Groom: {g_nadi}, Bride: {b_nadi}" +
                    (" (SAME — Nadi Dosha!)" if nadi_score == 0 else "")))

    return results


def _is_vashya_compatible(v1: str, v2: str) -> bool:
    """Check partial vashya compatibility."""
    # Nara is compatible with Nara and Jalchar
    # Chatushpada with Chatushpada
    # Others have partial compatibility
    compat = {
        ("Nara", "Jalchar"), ("Jalchar", "Nara"),
        ("Nara", "Chatushpada"), ("Chatushpada", "Nara"),
        ("Chatushpada", "Jalchar"), ("Jalchar", "Chatushpada"),
    }
    return (v1, v2) in compat


def _graha_maitri_score(lord1: str, lord2: str) -> float:
    """Score based on friendship between two rashi lords."""
    from .strength import FRIENDS, ENEMIES, NEUTRALS

    if lord1 == lord2:
        return 5.0

    l1_to_l2 = _relation(lord1, lord2)
    l2_to_l1 = _relation(lord2, lord1)

    # Both friends
    if l1_to_l2 == "friend" and l2_to_l1 == "friend":
        return 5.0
    # One friend, one neutral
    if {l1_to_l2, l2_to_l1} == {"friend", "neutral"}:
        return 4.0
    # Both neutral
    if l1_to_l2 == "neutral" and l2_to_l1 == "neutral":
        return 3.0
    # One friend, one enemy
    if {l1_to_l2, l2_to_l1} == {"friend", "enemy"}:
        return 1.0
    # One neutral, one enemy
    if {l1_to_l2, l2_to_l1} == {"neutral", "enemy"}:
        return 0.5
    # Both enemies
    if l1_to_l2 == "enemy" and l2_to_l1 == "enemy":
        return 0.0

    return 2.0


def _relation(planet1: str, planet2: str) -> str:
    """Get relationship of planet1 towards planet2."""
    from .strength import FRIENDS, ENEMIES, NEUTRALS

    if planet1 in ("Rahu", "Ketu") or planet2 in ("Rahu", "Ketu"):
        return "neutral"
    if planet2 in FRIENDS.get(planet1, []):
        return "friend"
    if planet2 in ENEMIES.get(planet1, []):
        return "enemy"
    return "neutral"
