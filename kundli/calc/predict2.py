"""Phase 2 — Prediction engine built on ChartAnalysis.

Uses the pre-computed ChartAnalysis (Phase 1) for maximum accuracy:

1. Monthly resolution (not quarterly/6-month)
2. 3-level Dasha scoring (Maha + Antar + Pratyantar)
3. Exact degree transits (not rashi-level)
4. Nakshatra lord chain influence
5. Dispositor chain influence
6. Navamsa confirmation (D9 dignity of dasha lord)
7. Ashtakavarga BAV/SAV for transit strength
8. Bhrigu Bindu activation (exact degree)
9. Yoga activation during dasha periods
10. Sade Sati with mitigation factors
11. Arudha Lagna for material manifestation
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import swisseph as swe

from ..models import Chart
from .analysis import ChartAnalysis, DashaPeriod, PlanetAnalysis
from .ashtakavarga import get_transit_score
from .bhrigu import (
    check_bb_activation, get_jupiter_cycle, get_planet_house_insight,
    get_saturn_cycle,
)
from .constants import AYANAMSHA, PLANETS, RASHIS
from .strength import ENEMIES, FRIENDS, RASHI_LORDS


# ---------------------------------------------------------------------------
# Transit computations (exact degree)
# ---------------------------------------------------------------------------

def _transit_position(jd: float, planet_id: int) -> tuple[float, int, bool]:
    """Get exact sidereal longitude, rashi index, and retrograde status."""
    swe.set_sid_mode(AYANAMSHA)
    result, _ = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    lon = result[0]
    speed = result[3]
    return lon, int(lon / 30) % 12, speed < 0


def _degree_distance(lon1: float, lon2: float) -> float:
    """Shortest angular distance between two longitudes."""
    d = abs(lon1 - lon2)
    return d if d <= 180 else 360 - d


def _check_transit_over_natal(transit_lon: float,
                               natal_positions: dict[str, float],
                               orb: float = 3.0) -> list[dict]:
    """Check if a transit planet is conjunct any natal planet (exact degree).

    Returns list of {planet, distance, exact} dicts.
    """
    hits = []
    for name, natal_lon in natal_positions.items():
        dist = _degree_distance(transit_lon, natal_lon)
        if dist <= orb:
            hits.append({
                "planet": name,
                "distance": round(dist, 2),
                "exact": dist <= 1.0,
            })
    return hits


# ---------------------------------------------------------------------------
# Dasha scoring
# ---------------------------------------------------------------------------

NATURE_SCORES = {
    "yogakaraka": 3.0, "benefic": 2.0, "kendradhipati": 0.5,
    "neutral": 0, "mixed": -0.5, "malefic": -2.0,
}


def _mutual_relation(p1: str, p2: str) -> tuple[str, float]:
    """5-fold Parashari mutual relationship with score."""
    if p1 == p2:
        return "same", 1.0
    shadow = {"Rahu": "Saturn", "Ketu": "Mars"}
    a = shadow.get(p1, p1)
    b = shadow.get(p2, p2)
    if a == b:
        return "friend", 1.0

    r1 = ("friend" if b in FRIENDS.get(a, []) else
          "enemy" if b in ENEMIES.get(a, []) else "neutral")
    r2 = ("friend" if a in FRIENDS.get(b, []) else
          "enemy" if a in ENEMIES.get(b, []) else "neutral")

    combo = {r1, r2}
    if combo == {"friend"}:
        return "best_friend", 1.5
    if combo == {"friend", "neutral"}:
        return "friend", 1.0
    if combo == {"neutral"}:
        return "neutral", 0
    if combo == {"enemy", "neutral"}:
        return "enemy", -1.0
    if combo == {"enemy"}:
        return "bitter_enemy", -1.5
    return "neutral", 0


def _score_dasha_period(ana: ChartAnalysis,
                        maha: DashaPeriod,
                        antar: Optional[DashaPeriod],
                        prat: Optional[DashaPeriod]) -> tuple[float, list[str]]:
    """Score the dasha combination using full ChartAnalysis."""
    score = 0.0
    notes = []

    mp = ana.planets.get(maha.lord)
    if not mp:
        return 0, []

    # --- Mahadasha lord ---
    # Nature
    score += NATURE_SCORES.get(mp.functional_nature, 0)

    # Strength (0-10 → -3 to +3)
    str_bonus = (mp.combined_strength - 5) * 0.6
    score += str_bonus

    # D9 confirmation: strong in navamsa = delivers promised results
    d9_map = {"Exalted": 1.5, "Own Sign": 1.0, "Mooltrikona": 1.2,
              "Friendly": 0.3, "Neutral": 0, "Enemy": -0.5, "Debilitated": -1.5}
    score += d9_map.get(mp.navamsa_dignity, 0)
    if mp.navamsa_dignity in ("Exalted", "Own Sign", "Mooltrikona"):
        notes.append(f"{maha.lord} strong in D9 ({mp.navamsa_dignity})")
    elif mp.navamsa_dignity == "Debilitated":
        notes.append(f"{maha.lord} debilitated in D9 — poor delivery")

    # Nakshatra chain influence
    nc = ana.nakshatra_chains.get(maha.lord)
    if nc and nc.chain:
        if nc.chain_strength >= 7:
            score += 1.0
            notes.append(f"Nak chain strong ({' → '.join(nc.chain)})")
        elif nc.chain_strength <= 3:
            score -= 1.0
            notes.append(f"Nak chain weak ({' → '.join(nc.chain)})")

    # Dispositor chain
    dc = ana.dispositor_chains.get(maha.lord)
    if dc:
        if dc.chain_strong:
            score += 0.5
        else:
            score -= 0.5
            notes.append(f"Dispositor {dc.final_dispositor} is weak")

    # Combustion
    if mp.is_combust:
        score -= 1.5
        notes.append(f"{maha.lord} combust — weakened results")

    notes.insert(0,
        f"Maha: {maha.lord} — {mp.functional_nature} "
        f"(str:{mp.combined_strength}/10, D1:{mp.dignity}, D9:{mp.navamsa_dignity})")

    # --- Antardasha lord ---
    if antar:
        ap = ana.planets.get(antar.lord)
        if ap:
            score += NATURE_SCORES.get(ap.functional_nature, 0) * 0.4
            score += (ap.combined_strength - 5) * 0.3

            # Mutual relationship
            rel_name, rel_score = _mutual_relation(maha.lord, antar.lord)
            score += rel_score

            # D9 of antardasha lord
            score += d9_map.get(ap.navamsa_dignity, 0) * 0.4

            notes.append(
                f"Antar: {antar.lord} — {ap.functional_nature} "
                f"(str:{ap.combined_strength}/10), relation: {rel_name}")

    # --- Pratyantar lord ---
    if prat:
        pp = ana.planets.get(prat.lord)
        if pp:
            score += NATURE_SCORES.get(pp.functional_nature, 0) * 0.15
            score += (pp.combined_strength - 5) * 0.1

            # Prat-Maha relation
            _, prel_score = _mutual_relation(maha.lord, prat.lord)
            score += prel_score * 0.3

            notes.append(f"Prat: {prat.lord} (str:{pp.combined_strength}/10)")

    return score, notes


# ---------------------------------------------------------------------------
# Yoga activation
# ---------------------------------------------------------------------------

_POSITIVE_YOGAS = {
    "Gajakesari Yoga", "Budhaditya Yoga", "Hamsa Yoga", "Malavya Yoga",
    "Bhadra Yoga", "Ruchaka Yoga", "Shasha Yoga", "Dhana Yoga",
    "Raja Yoga", "Viparita Raja Yoga", "Guru-Mangal Yoga",
    "Chandra-Mangal Yoga",
}
_NEGATIVE_YOGAS = {"Kemadruma Yoga", "Manglik Dosha"}

_MAHAPURUSHA_MAP = {
    "Ruchaka Yoga": "Mars", "Bhadra Yoga": "Mercury",
    "Hamsa Yoga": "Jupiter", "Malavya Yoga": "Venus", "Shasha Yoga": "Saturn",
}


def _yoga_activation(ana: ChartAnalysis,
                     maha_lord: str,
                     antar_lord: Optional[str]) -> tuple[float, list[str]]:
    """Check which yogas activate in current dasha."""
    score = 0.0
    notes = []
    lords = {maha_lord}
    if antar_lord:
        lords.add(antar_lord)

    for yoga_name, yoga_desc in ana.yogas:
        activated = False

        # Direct dasha lord mention
        for lord in lords:
            if lord in yoga_desc:
                activated = True

        # Mahapurusha
        if yoga_name in _MAHAPURUSHA_MAP:
            if _MAHAPURUSHA_MAP[yoga_name] in lords:
                activated = True

        # Specific checks
        if yoga_name == "Gajakesari Yoga" and lords & {"Jupiter", "Moon"}:
            activated = True
        elif yoga_name == "Budhaditya Yoga" and lords & {"Sun", "Mercury"}:
            activated = True

        if activated:
            if yoga_name in _POSITIVE_YOGAS:
                bonus = 2.0 if maha_lord in yoga_desc else 1.0
                score += bonus
                notes.append(f"{yoga_name} activated")
            elif yoga_name in _NEGATIVE_YOGAS:
                if yoga_name == "Kemadruma Yoga" and "Moon" in lords:
                    score -= 1.5
                    notes.append("Kemadruma Yoga felt")

    return score, notes


# ---------------------------------------------------------------------------
# Life area mapping
# ---------------------------------------------------------------------------

HOUSE_AREAS = {
    1:  "self", 2:  "wealth", 3:  "courage", 4:  "home",
    5:  "intellect", 6:  "enemies", 7:  "marriage",
    8:  "longevity", 9:  "fortune", 10: "career",
    11: "gains", 12: "loss",
}

LIFE_AREA_HOUSES = {
    "Career":        {10, 6, 2, 11},
    "Finance":       {2, 11, 5},
    "Relationships": {7, 1, 5},
    "Health":        {1, 6, 8},
    "Education":     {4, 5, 9},
    "Home/Property": {4},
    "Travel":        {3, 9, 12},
    "Spirituality":  {9, 12},
}

AREA_VARGAS = {
    "Career": 10, "Finance": 2, "Relationships": 9,
    "Education": 24, "Home/Property": 4, "Health": 1,
    "Travel": 3, "Spirituality": 20,
}


def _predict_life_areas(ana: ChartAnalysis, activated_houses: set[int],
                        base_score: float, maha_lord: str,
                        transit_context: dict) -> dict[str, dict]:
    """Generate life area predictions from ChartAnalysis."""
    areas = {}

    for area_name, area_houses in LIFE_AREA_HOUSES.items():
        relevant = activated_houses & area_houses
        if not relevant:
            continue

        area_score = base_score * 0.35

        for h in relevant:
            ha = ana.houses[h]

            # House lord strength
            lord_pa = ha.lord_planet
            if lord_pa:
                if lord_pa.combined_strength >= 7:
                    area_score += 1.5
                elif lord_pa.combined_strength <= 3:
                    area_score -= 1.5

                # Dignity
                if lord_pa.dignity in ("Exalted", "Own Sign", "Mooltrikona"):
                    area_score += 1.0
                elif lord_pa.dignity == "Debilitated":
                    area_score -= 1.0

            # Jupiter aspect on house = protection
            if "Jupiter" in ha.aspecting_planets:
                area_score += 0.5
            if "Saturn" in ha.aspecting_planets:
                area_score -= 0.3

            # Occupants
            for occ in ha.occupants:
                occ_pa = ana.planets.get(occ)
                if occ_pa:
                    if occ_pa.name in ("Jupiter", "Venus") and occ_pa.combined_strength >= 5:
                        area_score += 0.5
                    elif occ_pa.name in ("Saturn", "Rahu") and occ_pa.combined_strength <= 4:
                        area_score -= 0.3

        # Varga confirmation
        varga_div = AREA_VARGAS.get(area_name)
        if varga_div and varga_div in ana.vargas:
            vc = ana.vargas[varga_div]
            for pos in vc.positions:
                if pos.name == maha_lord:
                    if pos.house in {1, 4, 5, 7, 9, 10, 11}:
                        area_score += 0.5
                    elif pos.house in {6, 8, 12}:
                        area_score -= 0.5
                    break

        # Sade Sati
        if "sade_sati" in transit_context:
            if area_name == "Health":
                area_score -= 1.0
            elif area_name in ("Career", "Relationships"):
                area_score -= 0.5

        # Transit support
        jup_cycle = transit_context.get("jupiter_cycle", {})
        sat_cycle = transit_context.get("saturn_cycle", {})
        area_key = area_name.lower().split("/")[0]
        if jup_cycle.get(area_key):
            area_score += 0.5 if transit_context.get("jupiter_good") else 0.2
        if sat_cycle.get(area_key) and "difficult" in str(sat_cycle.get(area_key, "")).lower():
            area_score -= 0.3

        # Arudha check: dasha lord in houses from Arudha Lagna gives material results
        arudha_h = (ana.arudha_lagna_idx - ana.lagna_rashi_idx) % 12 + 1
        for h in relevant:
            maha_pa = ana.planets.get(maha_lord)
            if maha_pa:
                maha_from_arudha = ((maha_pa.rashi_idx - ana.arudha_lagna_idx) % 12) + 1
                if maha_from_arudha in {1, 2, 4, 5, 7, 9, 10, 11}:
                    area_score += 0.3
                    break

        # Outlook
        if area_score >= 3:
            outlook = "very_favorable"
        elif area_score >= 1:
            outlook = "favorable"
        elif area_score >= -1:
            outlook = "mixed"
        elif area_score >= -3:
            outlook = "challenging"
        else:
            outlook = "difficult"

        areas[area_name] = {
            "outlook": outlook,
            "score": round(area_score, 1),
            "houses": sorted(relevant),
        }

    if not areas:
        areas["General"] = {
            "outlook": "favorable" if base_score >= 1 else (
                "mixed" if base_score >= -1 else "challenging"),
            "score": round(base_score, 1),
            "houses": [],
        }

    return areas


# ---------------------------------------------------------------------------
# Main prediction engine
# ---------------------------------------------------------------------------

def generate_predictions(ana: ChartAnalysis,
                         start_year: int, end_year: int) -> tuple[list, dict, list]:
    """Generate monthly predictions using full ChartAnalysis.

    Args:
        ana: Pre-computed ChartAnalysis (Phase 1 output).
        start_year: First year.
        end_year: Last year (inclusive).

    Returns:
        (predictions_list, bav, sav)
    """
    swe.set_ephe_path(None)
    swe.set_sid_mode(AYANAMSHA)

    # Natal longitude map for exact degree transit checks
    natal_lons = {p.name: p.longitude for p in ana.chart.planets
                  if p.name != "Lagna"}

    predictions = []

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            mid_day = 15
            period_label = f"{_MONTH_NAMES[month]} {year}"

            mid_date = datetime(year, month, mid_day)
            utc_hour = 12 - 5.5
            jd = swe.julday(year, month, mid_day, utc_hour)

            # === Dasha (3 levels) ===
            maha, antar, prat = ana.get_dasha_at(mid_date)
            if not maha:
                continue

            # Dasha score
            dasha_score, analysis = _score_dasha_period(ana, maha, antar, prat)

            # === Transit computations (exact degree) ===
            transit_context = {}
            transit_score = 0.0

            # Jupiter transit
            jup_lon, jup_rashi_idx, jup_retro = _transit_position(jd, swe.JUPITER)
            jup_from_moon = ((jup_rashi_idx - ana.moon_rashi_idx) % 12) + 1
            jup_from_lagna = ((jup_rashi_idx - ana.lagna_rashi_idx) % 12) + 1
            jup_bindus, _ = get_transit_score(ana.bav, "Jupiter", jup_rashi_idx)
            jup_sav = ana.sav[jup_rashi_idx]

            # Exact degree transit: Jupiter over natal planets
            jup_natal_hits = _check_transit_over_natal(
                jup_lon, natal_lons, orb=3.0)

            jup_good_houses = {1, 2, 5, 7, 9, 11}
            jup_moon_good = jup_from_moon in jup_good_houses
            jup_lagna_good = jup_from_lagna in jup_good_houses

            if jup_moon_good and jup_lagna_good:
                bonus = 2.5 if jup_bindus >= 5 else 1.5
                transit_score += bonus
                transit_context["jupiter_good"] = True
            elif jup_moon_good or jup_lagna_good:
                bonus = 1.5 if jup_bindus >= 5 else 0.5
                transit_score += bonus
                transit_context["jupiter_good"] = True
            else:
                transit_score += (0 if jup_bindus >= 5 else -1.0)

            # Exact conjunctions amplify
            for hit in jup_natal_hits:
                if hit["exact"]:
                    if hit["planet"] in ("Venus", "Moon", "Mercury"):
                        transit_score += 1.5
                        analysis.append(
                            f"Jupiter exact over natal {hit['planet']} ({hit['distance']}°) — strong trigger")
                    else:
                        transit_score += 0.8
                        analysis.append(
                            f"Jupiter transit over {hit['planet']} ({hit['distance']}°)")
                elif hit["distance"] <= 2.0:
                    transit_score += 0.5

            # Bhrigu Jupiter cycle
            jup_cycle = get_jupiter_cycle(jup_from_lagna)
            transit_context["jupiter_cycle"] = jup_cycle

            analysis.append(
                f"Jupiter H{jup_from_moon}/Moon, H{jup_from_lagna}/Lagna "
                f"[BAV:{jup_bindus}/8, SAV:{jup_sav}]"
                f"{' ℞' if jup_retro else ''}")

            # Saturn transit
            sat_lon, sat_rashi_idx, sat_retro = _transit_position(jd, swe.SATURN)
            sat_from_moon = ((sat_rashi_idx - ana.moon_rashi_idx) % 12) + 1
            sat_from_lagna = ((sat_rashi_idx - ana.lagna_rashi_idx) % 12) + 1
            sat_bindus, _ = get_transit_score(ana.bav, "Saturn", sat_rashi_idx)

            # Saturn exact degree transit
            sat_natal_hits = _check_transit_over_natal(
                sat_lon, natal_lons, orb=3.0)

            for hit in sat_natal_hits:
                if hit["exact"]:
                    transit_score -= 1.0
                    analysis.append(
                        f"Saturn exact over natal {hit['planet']} ({hit['distance']}°) — pressure point")
                elif hit["distance"] <= 2.0:
                    transit_score -= 0.4

            sat_cycle = get_saturn_cycle(sat_from_lagna)
            transit_context["saturn_cycle"] = sat_cycle

            # Sade Sati
            sat_moon_diff = (sat_rashi_idx - ana.moon_rashi_idx) % 12
            sade_phase = None
            if sat_moon_diff == 11:
                sade_phase = "rising"
            elif sat_moon_diff == 0:
                sade_phase = "peak"
            elif sat_moon_diff == 1:
                sade_phase = "setting"

            if sade_phase:
                transit_context["sade_sati"] = sade_phase
                base_pen = {"rising": -1.5, "peak": -2.5, "setting": -1.0}[sade_phase]
                if sat_bindus >= 4:
                    base_pen *= 0.6
                # Jupiter aspect on Moon mitigates
                if "Jupiter" in ana.houses[
                    next(p.house for p in ana.chart.planets if p.name == "Moon")
                ].aspecting_planets if ana.houses else []:
                    base_pen *= 0.5
                    analysis.append("Jupiter aspects Moon — Sade Sati reduced")
                transit_score += base_pen
                analysis.append(
                    f"SADE SATI — {sade_phase} phase [BAV:{sat_bindus}/8]")
            else:
                sat_good = {3, 6, 11}
                if sat_from_moon in sat_good:
                    transit_score += (1.5 if sat_bindus >= 4 else 0.5)
                elif sat_from_moon in {1, 4, 7, 8, 10, 12}:
                    transit_score += (-0.5 if sat_bindus >= 4 else -1.5)

            # Rahu/Ketu transit
            rahu_lon, rahu_rashi_idx, _ = _transit_position(jd, swe.MEAN_NODE)
            rahu_from_lagna = ((rahu_rashi_idx - ana.lagna_rashi_idx) % 12) + 1
            if rahu_from_lagna in {1, 2, 5, 7, 8, 9}:
                transit_score -= 0.5

            # Rahu exact degree over natal planets
            rahu_natal_hits = _check_transit_over_natal(
                rahu_lon, natal_lons, orb=2.5)
            for hit in rahu_natal_hits:
                if hit["exact"]:
                    transit_score -= 0.8
                    analysis.append(
                        f"Rahu over natal {hit['planet']} — karmic disruption")

            # === Bhrigu Bindu ===
            bb_activations = check_bb_activation(ana.bhrigu_bindu, jd, orb=3.0)
            bb_data = None
            for act in bb_activations:
                if act["effect"] == "positive":
                    transit_score += 2.0
                else:
                    transit_score -= 1.0
                analysis.append(f"BB: {act['description']} (orb:{act['distance']}°)")
            if bb_activations:
                bb_data = {
                    "activated_by": [a["planet"] for a in bb_activations],
                    "rashi": ana.bhrigu_bindu.rashi,
                    "degree": f"{ana.bhrigu_bindu.rashi_degree:.1f}°",
                    "house": ana.bhrigu_bindu.house,
                }

            # === Yoga activation ===
            yoga_score, yoga_notes = _yoga_activation(
                ana, maha.lord, antar.lord if antar else None)
            analysis.extend(yoga_notes)

            # === Dasha Sandhi ===
            sandhi_penalty = 0
            days_to_maha_end = (maha.end - mid_date).days
            days_from_maha_start = (mid_date - maha.start).days
            if 0 < days_to_maha_end < 90:
                sandhi_penalty = -0.5
                analysis.append("Dasha sandhi — Maha transition approaching")
            elif 0 < days_from_maha_start < 90:
                sandhi_penalty = -0.5
                analysis.append("Dasha sandhi — settling into new Maha")

            # === Combined score ===
            total_score = dasha_score + transit_score + yoga_score + sandhi_penalty

            # === Activated houses (for life area prediction) ===
            activated_houses: set[int] = set()
            mp = ana.planets.get(maha.lord)
            if mp:
                activated_houses.update(mp.lordships)
                activated_houses.add(mp.house)
            if antar:
                ap = ana.planets.get(antar.lord)
                if ap:
                    activated_houses.update(ap.lordships)
                    activated_houses.add(ap.house)
            if prat:
                pp = ana.planets.get(prat.lord)
                if pp:
                    activated_houses.update(pp.lordships)
            activated_houses.discard(0)

            # === Life area predictions ===
            life_areas = _predict_life_areas(
                ana, activated_houses, total_score,
                maha.lord, transit_context)

            # === Outlook ===
            if total_score >= 4:
                outlook = "Very Favorable"
            elif total_score >= 1.5:
                outlook = "Favorable"
            elif total_score >= -1.5:
                outlook = "Mixed"
            elif total_score >= -4:
                outlook = "Challenging"
            else:
                outlook = "Difficult"

            dasha_label = maha.lord
            if antar:
                dasha_label += f"-{antar.lord}"
            if prat:
                dasha_label += f"-{prat.lord}"

            predictions.append({
                "period": period_label,
                "month": month,
                "year": year,
                "dasha": dasha_label,
                "outlook": outlook,
                "score": round(total_score, 1),
                "analysis": analysis,
                "life_areas": life_areas,
                "yogas_active": yoga_notes,
                "sade_sati": sade_phase,
                "bhrigu_bindu": bb_data,
                "jupiter_cycle": {
                    "house": jup_from_lagna,
                    "summary": jup_cycle.get("summary", ""),
                },
                "saturn_cycle": {
                    "house": sat_from_lagna,
                    "summary": sat_cycle.get("summary", ""),
                },
                "strength_method": "analysis_v2",
            })

    swe.close()
    return predictions, ana.bav, ana.sav


_MONTH_NAMES = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
