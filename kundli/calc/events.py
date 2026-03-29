"""Event timing engine — answers specific life questions.

Uses classical techniques:
1. Dasha lord relevance (house lordship + karaka)
2. Double Transit Theory (Jupiter + Saturn on relevant house/lord)
3. Bhrigu Bindu activation
4. Varga confirmation (D9 marriage, D10 career, etc.)
5. Transit of karaka planets

Reference: Uttara Kalamrita, Phaladeepika, Brihat Parashara Hora Shastra.
"""

from datetime import datetime, timedelta
from typing import NamedTuple

import swisseph as swe

from ..models import Chart
from .bhrigu import calculate_bhrigu_bindu
from .constants import AYANAMSHA, RASHIS
from .dasha import calculate_dasha
from .strength import RASHI_LORDS, get_dignity
from .vargas import calculate_varga
from .ashtakavarga import calculate_bav, get_transit_score


# ===== Event definitions =====

class EventDef(NamedTuple):
    """Definition of a life event for timing analysis."""
    name: str
    houses: tuple[int, ...]        # Primary houses
    karakas: tuple[str, ...]       # Significator planets
    varga: int                      # Relevant divisional chart
    question: str                   # Display question


EVENTS = {
    "marriage": EventDef(
        "Marriage", (7, 1), ("Venus",), 9,
        "When will marriage happen?"),
    "job": EventDef(
        "Job/Career Start", (10, 6), ("Saturn",), 10,
        "When will I get a job or career breakthrough?"),
    "job_switch": EventDef(
        "Job Change", (3, 10, 6), ("Rahu", "Saturn"), 10,
        "When is a good time to switch jobs?"),
    "property": EventDef(
        "Property/Vehicle", (4,), ("Mars", "Venus"), 4,
        "When will I buy property or vehicle?"),
    "children": EventDef(
        "Children", (5,), ("Jupiter",), 7,
        "When will I have children?"),
    "foreign_travel": EventDef(
        "Foreign Travel/Settlement", (12, 9), ("Rahu",), 4,
        "When will I travel or settle abroad?"),
    "wealth": EventDef(
        "Wealth/Financial Gains", (2, 11), ("Jupiter",), 2,
        "When will I gain significant wealth?"),
    "education": EventDef(
        "Education/Exams", (4, 5, 9), ("Jupiter", "Mercury"), 24,
        "When will I succeed in education or exams?"),
    "health_recovery": EventDef(
        "Health Recovery", (1, 6), ("Sun",), 1,
        "When will my health improve?"),
    "relationship_trouble": EventDef(
        "Relationship Challenges", (7, 8), ("Saturn", "Mars"), 9,
        "When might I face relationship difficulties?"),
    "spiritual_growth": EventDef(
        "Spiritual Progress", (9, 12), ("Ketu", "Jupiter"), 20,
        "When will spiritual growth accelerate?"),
    "business_start": EventDef(
        "Business/Entrepreneurship", (7, 10, 11), ("Mercury", "Jupiter"), 10,
        "When is a good time to start a business?"),
}


def _get_house_lordships(lagna_rashi_idx: int) -> dict[int, str]:
    """House number -> lord planet name."""
    return {
        h: RASHI_LORDS[RASHIS[(lagna_rashi_idx + h - 1) % 12]]
        for h in range(1, 13)
    }


def _planet_lordships(lagna_rashi_idx: int) -> dict[str, list[int]]:
    """Planet -> list of houses it lords."""
    lordships: dict[str, list[int]] = {}
    for h in range(1, 13):
        rashi = RASHIS[(lagna_rashi_idx + h - 1) % 12]
        lord = RASHI_LORDS[rashi]
        lordships.setdefault(lord, []).append(h)
    return lordships


def _check_double_transit(jd: float, target_rashi_idxs: set[int],
                          bav: dict) -> dict:
    """Check if Jupiter AND Saturn both aspect target rashis.

    Jupiter aspects: 5th, 7th, 9th from its position.
    Saturn aspects: 3rd, 7th, 10th from its position.

    Returns dict with jupiter/saturn positions and whether double transit hits.
    """
    swe.set_sid_mode(AYANAMSHA)

    jup_result, _ = swe.calc_ut(jd, swe.JUPITER, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    sat_result, _ = swe.calc_ut(jd, swe.SATURN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)

    jup_rashi = int(jup_result[0] / 30) % 12
    sat_rashi = int(sat_result[0] / 30) % 12

    # Rashis aspected by Jupiter (1st, 5th, 7th, 9th from Jupiter)
    jup_aspects = {jup_rashi, (jup_rashi + 4) % 12, (jup_rashi + 6) % 12, (jup_rashi + 8) % 12}

    # Rashis aspected by Saturn (1st, 3rd, 7th, 10th from Saturn)
    sat_aspects = {sat_rashi, (sat_rashi + 2) % 12, (sat_rashi + 6) % 12, (sat_rashi + 9) % 12}

    jup_hits = jup_aspects & target_rashi_idxs
    sat_hits = sat_aspects & target_rashi_idxs

    # Double transit = both hit at least one target
    double_transit = bool(jup_hits) and bool(sat_hits)

    # BAV strength for Jupiter in its current rashi
    jup_bindus, _ = get_transit_score(bav, "Jupiter", jup_rashi)
    sat_bindus, _ = get_transit_score(bav, "Saturn", sat_rashi)

    return {
        "double_transit": double_transit,
        "jupiter_rashi": RASHIS[jup_rashi],
        "jupiter_house_hits": jup_hits,
        "saturn_rashi": RASHIS[sat_rashi],
        "saturn_house_hits": sat_hits,
        "jupiter_bav": jup_bindus,
        "saturn_bav": sat_bindus,
        "strength": "strong" if (jup_bindus >= 5 and double_transit) else
                    "good" if double_transit else
                    "partial" if (jup_hits or sat_hits) else "none",
    }


def _dasha_relevance(lord: str, event: EventDef,
                     house_lords: dict[int, str],
                     planet_lords: dict[str, list[int]]) -> tuple[float, str]:
    """Score how relevant a dasha lord is for an event (0-10)."""
    score = 0.0
    reason = ""

    # Is the dasha lord the lord of a relevant house?
    lord_houses = set(planet_lords.get(lord, []))
    relevant_houses = set(event.houses)
    overlap = lord_houses & relevant_houses

    if overlap:
        score += 5.0
        reason = f"{lord} lords H{','.join(str(h) for h in sorted(overlap))}"

    # Is the dasha lord a karaka for this event?
    if lord in event.karakas:
        score += 3.0
        reason += f"{', ' if reason else ''}{lord} is karaka"

    # Is the dasha lord placed in a relevant house?
    # (We'd need planet positions — handled at call site)

    # Does the dasha lord have secondary connection?
    # Lord of house where relevant house lord sits
    for h in event.houses:
        h_lord = house_lords.get(h, "")
        if h_lord == lord:
            continue
        # Check if dasha lord and house lord are friends
        from .strength import FRIENDS
        if lord in FRIENDS.get(h_lord, []):
            score += 1.0
            break

    return min(10, score), reason


def predict_event(chart: Chart, event_key: str,
                  start_year: int, end_year: int) -> dict:
    """Predict timing for a specific life event.

    Args:
        chart: Natal chart.
        event_key: Key from EVENTS dict (e.g., "marriage", "job").
        start_year: Start of search window.
        end_year: End of search window.

    Returns:
        Dict with windows (favorable periods), analysis, and recommendations.
    """
    if event_key not in EVENTS:
        return {"error": f"Unknown event: {event_key}"}

    event = EVENTS[event_key]
    swe.set_ephe_path(None)
    swe.set_sid_mode(AYANAMSHA)

    lagna_rashi_idx = int(chart.lagna.longitude / 30) % 12
    moon = next(p for p in chart.planets if p.name == "Moon")
    moon_rashi_idx = int(moon.longitude / 30) % 12

    house_lords = _get_house_lordships(lagna_rashi_idx)
    planet_lords = _planet_lordships(lagna_rashi_idx)
    all_planets = {p.name: p for p in chart.planets}

    dashas = calculate_dasha(chart)
    bav = calculate_bav(chart)
    bb = calculate_bhrigu_bindu(chart)

    # Target rashis for double transit
    # = rashi of each relevant house + rashi where house lord sits
    target_rashis = set()
    event_analysis = []
    house_details = []

    for h in event.houses:
        h_rashi_idx = (lagna_rashi_idx + h - 1) % 12
        target_rashis.add(h_rashi_idx)

        h_lord = house_lords[h]
        h_lord_planet = all_planets.get(h_lord)
        if h_lord_planet:
            lord_rashi_idx = int(h_lord_planet.longitude / 30) % 12
            target_rashis.add(lord_rashi_idx)

            dignity = get_dignity(h_lord_planet)
            house_details.append({
                "house": h,
                "lord": h_lord,
                "lord_rashi": h_lord_planet.rashi,
                "lord_house": h_lord_planet.house,
                "dignity": dignity,
            })

            if dignity in ("Exalted", "Own Sign", "Mooltrikona"):
                event_analysis.append(
                    f"H{h} lord {h_lord} is {dignity} in {h_lord_planet.rashi} (H{h_lord_planet.house}) — strong for {event.name}")
            elif dignity == "Debilitated":
                event_analysis.append(
                    f"H{h} lord {h_lord} is Debilitated — delays in {event.name}")

        # Planets in this house — Bhrigu insight
        for p in chart.planets:
            if p.house == h:
                from .bhrigu import get_planet_house_insight
                insight = get_planet_house_insight(p.name, h)
                if insight:
                    event_analysis.append(f"{p.name} in H{h}: {insight[:80]}")

    # Varga confirmation
    varga_chart = calculate_varga(chart, event.varga)
    varga_notes = []
    for pos in varga_chart.positions:
        if pos.name in [house_lords[h] for h in event.houses]:
            varga_notes.append(
                f"{pos.name} in {pos.rashi} (H{pos.house}) in D{event.varga}")
            if pos.house in {1, 4, 5, 7, 9, 10, 11}:
                event_analysis.append(
                    f"D{event.varga} confirms: {pos.name} well placed in H{pos.house}")
            elif pos.house in {6, 8, 12}:
                event_analysis.append(
                    f"D{event.varga} caution: {pos.name} in H{pos.house} — delays possible")

    # ---- Scan time windows ----
    windows = []

    for year in range(start_year, end_year + 1):
        for month_start in range(1, 13, 3):  # Quarterly scan
            month_end = min(month_start + 2, 12)
            mid_month = month_start + 1
            if mid_month > 12:
                mid_month = 12

            mid_date = datetime(year, mid_month, 15)
            utc_hour = 12 - 5.5
            jd = swe.julday(year, mid_month, 15, utc_hour)

            # 1. Find current dasha
            maha_lord = None
            antar_lord = None
            for lord, d_start, d_end, antardashas in dashas:
                if d_start <= mid_date < d_end:
                    maha_lord = lord
                    for al, a_start, a_end in antardashas:
                        if a_start <= mid_date < a_end:
                            antar_lord = al
                            break
                    break

            if not maha_lord:
                continue

            # 2. Score dasha relevance
            maha_score, maha_reason = _dasha_relevance(
                maha_lord, event, house_lords, planet_lords)
            antar_score, antar_reason = 0, ""
            if antar_lord:
                antar_score, antar_reason = _dasha_relevance(
                    antar_lord, event, house_lords, planet_lords)

            # Bonus: dasha lord placed in relevant house
            maha_planet = all_planets.get(maha_lord)
            if maha_planet and maha_planet.house in event.houses:
                maha_score += 2.0
                maha_reason += f", placed in H{maha_planet.house}"

            dasha_total = maha_score * 0.6 + antar_score * 0.4

            # 3. Double transit check
            dt = _check_double_transit(jd, target_rashis, bav)

            # 4. Bhrigu Bindu check
            from .bhrigu import check_bb_activation
            bb_activations = check_bb_activation(bb, jd, orb=5.0)
            bb_bonus = 0
            bb_note = ""
            for act in bb_activations:
                if act["effect"] == "positive":
                    bb_bonus = 2
                    bb_note = f"Bhrigu Bindu activated by {act['planet']}"
                elif act["effect"] == "karmic" and event_key in ("marriage", "job", "property"):
                    bb_bonus = 1
                    bb_note = f"Saturn on Bhrigu Bindu — karmic event trigger"

            # 5. Combined window score
            window_score = 0.0
            reasons = []

            if dasha_total >= 4:
                window_score += 3.0
                reasons.append(f"Dasha: {maha_lord}-{antar_lord} ({maha_reason})")
            elif dasha_total >= 2:
                window_score += 1.5
                reasons.append(f"Dasha: {maha_lord}-{antar_lord} (moderate)")

            if dt["double_transit"]:
                window_score += 3.0
                reasons.append(f"Double transit active (Jup+Sat)")
            elif dt["strength"] == "partial":
                window_score += 1.0
                reasons.append(f"Partial transit support")

            if bb_bonus:
                window_score += bb_bonus
                reasons.append(bb_note)

            # Strong BAV bonus
            if dt["jupiter_bav"] >= 5:
                window_score += 0.5

            # Determine window quality
            if window_score >= 5:
                quality = "highly_probable"
            elif window_score >= 3:
                quality = "probable"
            elif window_score >= 1.5:
                quality = "possible"
            else:
                quality = "unlikely"
                continue  # Skip unlikely windows

            month_names = [
                "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
            ]
            period_label = f"{month_names[month_start]}-{month_names[month_end]} {year}"

            windows.append({
                "period": period_label,
                "year": year,
                "quarter": (month_start - 1) // 3 + 1,
                "score": round(window_score, 1),
                "quality": quality,
                "dasha": f"{maha_lord}-{antar_lord}" if antar_lord else maha_lord,
                "double_transit": dt["double_transit"],
                "bhrigu_bindu": bb_note if bb_bonus else None,
                "reasons": reasons,
            })

    # Sort by score descending
    windows.sort(key=lambda w: w["score"], reverse=True)

    # Consolidate — merge adjacent quarters of same quality
    best_windows = windows[:12]  # Top 12 windows

    swe.close()

    return {
        "event": event.name,
        "question": event.question,
        "houses": list(event.houses),
        "karakas": list(event.karakas),
        "house_details": house_details,
        "natal_analysis": event_analysis,
        "varga_notes": varga_notes,
        "bhrigu_bindu": {
            "longitude": bb.longitude,
            "rashi": bb.rashi,
            "degree": f"{bb.rashi_degree:.1f}°",
            "house": bb.house,
        },
        "windows": best_windows,
        "best_period": best_windows[0] if best_windows else None,
        "total_windows_found": len(windows),
    }


def predict_all_events(chart: Chart, start_year: int, end_year: int) -> dict[str, dict]:
    """Predict timing for all common life events."""
    results = {}
    for key in EVENTS:
        results[key] = predict_event(chart, key, start_year, end_year)
    return results
