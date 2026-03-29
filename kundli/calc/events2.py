"""Phase 2b — Event timing engine built on ChartAnalysis.

Answers specific life questions with monthly precision using:
1. 3-level Dasha relevance (Maha + Antar + Pratyantar)
2. Double Transit Theory (exact degree, not rashi-level)
3. Bhrigu Bindu activation
4. Varga confirmation (D9, D10, etc.)
5. Nakshatra lord chain scoring
6. Dispositor chain health
7. Transit over natal positions (exact degree)
8. BAV/SAV transit strength
9. Arudha Pada activation
"""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple

import swisseph as swe

from ..models import Chart
from .analysis import ChartAnalysis, DashaPeriod
from .ashtakavarga import get_transit_score
from .bhrigu import check_bb_activation, get_planet_house_insight
from .constants import AYANAMSHA, RASHIS
from .strength import FRIENDS, RASHI_LORDS


# ===== Event definitions =====

class EventDef(NamedTuple):
    name: str
    houses: tuple[int, ...]
    karakas: tuple[str, ...]
    varga: int
    question: str


EVENTS = {
    "marriage": EventDef(
        "Marriage", (7, 1, 2), ("Venus",), 9,
        "When will marriage happen?"),
    "job": EventDef(
        "Job/Career Start", (10, 6, 2), ("Saturn", "Sun"), 10,
        "When will I get a job or career breakthrough?"),
    "job_switch": EventDef(
        "Job Change", (3, 10, 6), ("Rahu", "Saturn"), 10,
        "When is a good time to switch jobs?"),
    "property": EventDef(
        "Property/Vehicle", (4, 11), ("Mars", "Venus"), 4,
        "When will I buy property or vehicle?"),
    "children": EventDef(
        "Children", (5, 2), ("Jupiter",), 7,
        "When will I have children?"),
    "foreign_travel": EventDef(
        "Foreign Travel/Settlement", (12, 9, 3), ("Rahu",), 4,
        "When will I travel or settle abroad?"),
    "wealth": EventDef(
        "Wealth/Financial Gains", (2, 11, 5), ("Jupiter",), 2,
        "When will I gain significant wealth?"),
    "education": EventDef(
        "Education/Exams", (4, 5, 9), ("Jupiter", "Mercury"), 24,
        "When will I succeed in education or exams?"),
    "health_recovery": EventDef(
        "Health Recovery", (1, 6, 8), ("Sun",), 1,
        "When will my health improve?"),
    "relationship_trouble": EventDef(
        "Relationship Challenges", (7, 8, 6), ("Saturn", "Mars"), 9,
        "When might I face relationship difficulties?"),
    "spiritual_growth": EventDef(
        "Spiritual Progress", (9, 12, 5), ("Ketu", "Jupiter"), 20,
        "When will spiritual growth accelerate?"),
    "business_start": EventDef(
        "Business/Entrepreneurship", (7, 10, 11, 3), ("Mercury", "Jupiter"), 10,
        "When is a good time to start a business?"),
}


# ===== Helpers =====

def _transit_lon(jd: float, planet_id: int) -> float:
    """Get exact sidereal longitude."""
    swe.set_sid_mode(AYANAMSHA)
    result, _ = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return result[0]


def _degree_dist(a: float, b: float) -> float:
    d = abs(a - b)
    return d if d <= 180 else 360 - d


def _check_double_transit_exact(jd: float, target_rashis: set[int],
                                 target_degrees: list[float],
                                 bav: dict) -> dict:
    """Double Transit Theory with both rashi-level and degree-level checks.

    Jupiter aspects: 1st, 5th, 7th, 9th from position.
    Saturn aspects: 1st, 3rd, 7th, 10th from position.
    """
    jup_lon = _transit_lon(jd, swe.JUPITER)
    sat_lon = _transit_lon(jd, swe.SATURN)

    jup_rashi = int(jup_lon / 30) % 12
    sat_rashi = int(sat_lon / 30) % 12

    jup_aspects = {jup_rashi, (jup_rashi + 4) % 12,
                   (jup_rashi + 6) % 12, (jup_rashi + 8) % 12}
    sat_aspects = {sat_rashi, (sat_rashi + 2) % 12,
                   (sat_rashi + 6) % 12, (sat_rashi + 9) % 12}

    jup_hits = jup_aspects & target_rashis
    sat_hits = sat_aspects & target_rashis
    double_transit = bool(jup_hits) and bool(sat_hits)

    # Exact degree bonus: Jupiter/Saturn near exact natal degree
    degree_bonus = 0.0
    for deg in target_degrees:
        if _degree_dist(jup_lon, deg) <= 3.0:
            degree_bonus += 1.0
            if _degree_dist(jup_lon, deg) <= 1.0:
                degree_bonus += 0.5  # Exact hit
        if _degree_dist(sat_lon, deg) <= 3.0:
            degree_bonus += 0.5

    jup_bindus, _ = get_transit_score(bav, "Jupiter", jup_rashi)
    sat_bindus, _ = get_transit_score(bav, "Saturn", sat_rashi)

    return {
        "double_transit": double_transit,
        "jupiter_rashi": RASHIS[jup_rashi],
        "saturn_rashi": RASHIS[sat_rashi],
        "jup_hits": jup_hits,
        "sat_hits": sat_hits,
        "jup_bindus": jup_bindus,
        "sat_bindus": sat_bindus,
        "degree_bonus": degree_bonus,
        "strength": ("strong" if (jup_bindus >= 5 and double_transit) else
                     "good" if double_transit else
                     "partial" if (jup_hits or sat_hits) else "none"),
    }


def _dasha_relevance(ana: ChartAnalysis, lord: str,
                     event: EventDef) -> tuple[float, list[str]]:
    """Score dasha lord relevance for an event (0-10).

    Uses: lordship, karaka, placement, nakshatra chain, dispositor,
    navamsa confirmation, friendship with house lords.
    """
    pa = ana.planets.get(lord)
    if not pa:
        return 0, []

    score = 0.0
    reasons = []

    # 1. Lordship of relevant house
    relevant_houses = set(event.houses)
    overlap = set(pa.lordships) & relevant_houses
    if overlap:
        score += 4.0
        reasons.append(f"lords H{','.join(str(h) for h in sorted(overlap))}")

    # 2. Karaka status
    if lord in event.karakas:
        score += 2.5
        reasons.append(f"karaka for {event.name}")

    # 3. Placed in relevant house
    if pa.house in relevant_houses:
        score += 2.0
        reasons.append(f"placed in H{pa.house}")

    # 4. Navamsa confirmation
    if event.varga in ana.vargas:
        vc = ana.vargas[event.varga]
        for pos in vc.positions:
            if pos.name == lord:
                if pos.house in {1, 4, 5, 7, 9, 10, 11}:
                    score += 1.0
                    reasons.append(f"D{event.varga} H{pos.house}")
                elif pos.house in {6, 8, 12}:
                    score -= 0.5
                break

    # 5. Nakshatra chain — if chain contains house lord of relevant house
    nc = ana.nakshatra_chains.get(lord)
    if nc:
        for chain_planet in nc.chain:
            chain_pa = ana.planets.get(chain_planet)
            if chain_pa and set(chain_pa.lordships) & relevant_houses:
                score += 1.0
                reasons.append(f"nak chain → {chain_planet} (H{''.join(str(h) for h in chain_pa.lordships)})")
                break

    # 6. Dispositor connection
    dc = ana.dispositor_chains.get(lord)
    if dc and dc.final_dispositor != lord:
        fd_pa = ana.planets.get(dc.final_dispositor)
        if fd_pa and set(fd_pa.lordships) & relevant_houses:
            score += 0.5

    # 7. Friendship with relevant house lords
    for h in event.houses:
        h_lord = ana.house_lord(h)
        if h_lord != lord and lord in FRIENDS.get(h_lord, []):
            score += 0.5
            break

    return min(10, score), reasons


# ===== Main engine =====

def predict_event(ana: ChartAnalysis, event_key: str,
                  start_year: int, end_year: int) -> dict:
    """Predict timing for a specific life event using ChartAnalysis.

    Monthly resolution with full classical technique integration.
    """
    if event_key not in EVENTS:
        return {"error": f"Unknown event: {event_key}"}

    event = EVENTS[event_key]
    swe.set_ephe_path(None)
    swe.set_sid_mode(AYANAMSHA)

    # === Natal analysis ===
    event_analysis = []
    house_details = []

    # Target rashis + exact degrees for double transit
    target_rashis: set[int] = set()
    target_degrees: list[float] = []

    for h in event.houses:
        ha = ana.houses[h]
        h_rashi_idx = ha.rashi_idx
        target_rashis.add(h_rashi_idx)

        lord_pa = ha.lord_planet
        if lord_pa:
            target_rashis.add(lord_pa.rashi_idx)
            target_degrees.append(lord_pa.longitude)

            house_details.append({
                "house": h,
                "lord": ha.lord,
                "lord_rashi": lord_pa.rashi,
                "lord_house": lord_pa.house,
                "dignity": lord_pa.dignity,
                "d9_dignity": lord_pa.navamsa_dignity,
                "strength": lord_pa.combined_strength,
            })

            # Natal analysis notes
            if lord_pa.dignity in ("Exalted", "Own Sign", "Mooltrikona"):
                event_analysis.append(
                    f"H{h} lord {ha.lord} is {lord_pa.dignity} in "
                    f"{lord_pa.rashi} (H{lord_pa.house}) — strong for {event.name}")
            elif lord_pa.dignity == "Debilitated":
                event_analysis.append(
                    f"H{h} lord {ha.lord} Debilitated — delays in {event.name}")

            # D9 check
            if lord_pa.navamsa_dignity in ("Exalted", "Own Sign"):
                event_analysis.append(
                    f"H{h} lord {ha.lord} strong in D9 ({lord_pa.navamsa_dignity}) — confirms")
            elif lord_pa.navamsa_dignity == "Debilitated":
                event_analysis.append(
                    f"H{h} lord {ha.lord} debilitated in D9 — weakens promise")

            # Dispositor chain
            dc = ana.dispositor_chains.get(ha.lord)
            if dc and not dc.chain_strong:
                event_analysis.append(
                    f"H{h} lord dispositor chain weak (→ {dc.final_dispositor})")

        # Occupants — Bhrigu insight
        for occ_name in ha.occupants:
            insight = get_planet_house_insight(occ_name, h)
            if insight:
                event_analysis.append(f"{occ_name} in H{h}: {insight[:80]}")

    # Karaka analysis
    for karaka in event.karakas:
        kp = ana.planets.get(karaka)
        if kp:
            target_degrees.append(kp.longitude)
            if kp.combined_strength >= 7:
                event_analysis.append(
                    f"Karaka {karaka} is strong ({kp.combined_strength}/10) — supports {event.name}")
            elif kp.combined_strength <= 3:
                event_analysis.append(
                    f"Karaka {karaka} is weak ({kp.combined_strength}/10) — challenges for {event.name}")

    # Varga confirmation
    varga_notes = []
    if event.varga in ana.vargas:
        vc = ana.vargas[event.varga]
        for h in event.houses:
            h_lord = ana.house_lord(h)
            for pos in vc.positions:
                if pos.name == h_lord:
                    varga_notes.append(
                        f"{pos.name} in {pos.rashi} (H{pos.house}) in D{event.varga}")
                    if pos.house in {1, 4, 5, 7, 9, 10, 11}:
                        event_analysis.append(
                            f"D{event.varga}: {pos.name} well placed in H{pos.house}")
                    elif pos.house in {6, 8, 12}:
                        event_analysis.append(
                            f"D{event.varga}: {pos.name} in H{pos.house} — delays")
                    break

    # Arudha Pada check for relevant houses
    for h in event.houses:
        arudha_idx = ana.houses[h].arudha_rashi_idx
        if arudha_idx >= 0:
            # If Arudha Pada falls in a good house from lagna
            arudha_house = (arudha_idx - ana.lagna_rashi_idx) % 12 + 1
            if arudha_house in {1, 4, 5, 7, 9, 10, 11}:
                event_analysis.append(
                    f"Arudha of H{h} in H{arudha_house} — material manifestation supported")

    # === Monthly scan ===
    windows = []

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            mid_date = datetime(year, month, 15)
            utc_hour = 12 - 5.5
            jd = swe.julday(year, month, 15, utc_hour)

            # 1. Find dasha (3 levels)
            maha, antar, prat = ana.get_dasha_at(mid_date)
            if not maha:
                continue

            # 2. Dasha relevance scoring
            maha_score, maha_reasons = _dasha_relevance(ana, maha.lord, event)
            antar_score, antar_reasons = (0, [])
            if antar:
                antar_score, antar_reasons = _dasha_relevance(
                    ana, antar.lord, event)
            prat_score, prat_reasons = (0, [])
            if prat:
                prat_score, prat_reasons = _dasha_relevance(
                    ana, prat.lord, event)

            # Weighted dasha total
            dasha_total = (maha_score * 0.5 +
                          antar_score * 0.3 +
                          prat_score * 0.2)

            # 3. Double transit (exact degree)
            dt = _check_double_transit_exact(
                jd, target_rashis, target_degrees, ana.bav)

            # 4. Bhrigu Bindu
            bb_activations = check_bb_activation(ana.bhrigu_bindu, jd, orb=4.0)
            bb_bonus = 0.0
            bb_note = ""
            for act in bb_activations:
                if act["effect"] == "positive":
                    bb_bonus = 2.0
                    if act["distance"] <= 1.0:
                        bb_bonus = 3.0  # Exact BB activation
                    bb_note = f"BB activated by {act['planet']} ({act['distance']}°)"
                elif act["effect"] == "karmic":
                    bb_bonus = 1.0
                    bb_note = f"Saturn on BB — karmic trigger ({act['distance']}°)"

            # 5. Combined window score
            window_score = 0.0
            reasons = []

            # Dasha contribution
            if dasha_total >= 4:
                window_score += 3.0
                r = f"Dasha: {maha.lord}"
                if antar:
                    r += f"-{antar.lord}"
                if prat:
                    r += f"-{prat.lord}"
                combined_reasons = maha_reasons + antar_reasons
                if combined_reasons:
                    r += f" ({'; '.join(combined_reasons[:3])})"
                reasons.append(r)
            elif dasha_total >= 2:
                window_score += 1.5
                reasons.append(f"Dasha: {maha.lord}-{antar.lord if antar else ''} (moderate)")

            # Double transit contribution
            if dt["double_transit"]:
                base_dt = 3.0
                base_dt += dt["degree_bonus"]
                window_score += base_dt
                reasons.append(f"Double transit (Jup+Sat)")
                if dt["degree_bonus"] >= 1.0:
                    reasons.append(f"Exact degree transit (+{dt['degree_bonus']:.1f})")
            elif dt["strength"] == "partial":
                window_score += 1.0 + dt["degree_bonus"] * 0.5
                reasons.append("Partial transit support")

            # BB contribution
            if bb_bonus:
                window_score += bb_bonus
                reasons.append(bb_note)

            # BAV bonus
            if dt["jup_bindus"] >= 5:
                window_score += 0.5
            if dt["sat_bindus"] >= 5 and dt["double_transit"]:
                window_score += 0.3

            # Pratyantar precision bonus: if prat lord is also relevant
            if prat and prat_score >= 3:
                window_score += 1.0
                reasons.append(f"Prat {prat.lord} also relevant")

            # Determine quality
            if window_score >= 6:
                quality = "highly_probable"
            elif window_score >= 4:
                quality = "probable"
            elif window_score >= 2:
                quality = "possible"
            else:
                continue  # Skip unlikely

            month_names = [
                "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
            ]

            dasha_label = maha.lord
            if antar:
                dasha_label += f"-{antar.lord}"
            if prat:
                dasha_label += f"-{prat.lord}"

            windows.append({
                "period": f"{month_names[month]} {year}",
                "year": year,
                "month": month,
                "score": round(window_score, 1),
                "quality": quality,
                "dasha": dasha_label,
                "double_transit": dt["double_transit"],
                "bhrigu_bindu": bb_note if bb_bonus else None,
                "reasons": reasons,
            })

    # Sort by score
    windows.sort(key=lambda w: w["score"], reverse=True)

    # Merge adjacent months of same quality into ranges
    merged = _merge_windows(windows[:20])

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
            "longitude": ana.bhrigu_bindu.longitude,
            "rashi": ana.bhrigu_bindu.rashi,
            "degree": f"{ana.bhrigu_bindu.rashi_degree:.1f}°",
            "house": ana.bhrigu_bindu.house,
        },
        "windows": merged,
        "best_period": merged[0] if merged else None,
        "total_windows": len(windows),
    }


def _merge_windows(windows: list[dict]) -> list[dict]:
    """Merge consecutive months with same quality into date ranges."""
    if not windows:
        return []

    # Sort by time
    by_time = sorted(windows, key=lambda w: (w["year"], w["month"]))

    merged = []
    current = dict(by_time[0])
    current["start_month"] = current["month"]
    current["start_year"] = current["year"]

    for w in by_time[1:]:
        # Check if consecutive and same quality
        prev_ym = current["year"] * 12 + current["month"]
        this_ym = w["year"] * 12 + w["month"]

        if (this_ym - prev_ym <= 2 and
            w["quality"] == current["quality"] and
            w["dasha"].split("-")[0] == current["dasha"].split("-")[0]):
            # Extend current range
            current["month"] = w["month"]
            current["year"] = w["year"]
            current["score"] = max(current["score"], w["score"])
            # Merge reasons
            for r in w["reasons"]:
                if r not in current["reasons"]:
                    current["reasons"].append(r)
            if w.get("double_transit"):
                current["double_transit"] = True
            if w.get("bhrigu_bindu") and not current.get("bhrigu_bindu"):
                current["bhrigu_bindu"] = w["bhrigu_bindu"]
        else:
            # Finalize current and start new
            _finalize_period(current)
            merged.append(current)
            current = dict(w)
            current["start_month"] = current["month"]
            current["start_year"] = current["year"]

    _finalize_period(current)
    merged.append(current)

    # Re-sort by score
    merged.sort(key=lambda w: w["score"], reverse=True)
    return merged[:12]


def _finalize_period(w: dict):
    """Create a clean period label from start/end months."""
    month_names = [
        "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    sm = w.get("start_month", w["month"])
    sy = w.get("start_year", w["year"])
    em = w["month"]
    ey = w["year"]

    if sy == ey and sm == em:
        w["period"] = f"{month_names[sm]} {sy}"
    elif sy == ey:
        w["period"] = f"{month_names[sm]}-{month_names[em]} {sy}"
    else:
        w["period"] = f"{month_names[sm]} {sy} - {month_names[em]} {ey}"

    # Clean up temp keys
    w.pop("start_month", None)
    w.pop("start_year", None)
