"""Prediction engine — Parashari + Bhrigu Samhita combined.

Integrates all classical Vedic techniques for maximum accuracy:

PARASHARI (BPHS):
- Vimshottari Dasha with Antardasha
- 16 Divisional Charts (Shodasha Varga)
- Vimshopaka Bala (varga-based strength)
- Shadbala (6-fold planetary strength)
- Ashtakavarga (BAV/SAV transit scoring)
- Yoga activation during dasha periods
- Graha Drishti (aspects)

BHRIGU SAMHITA:
- Bhrigu Bindu (Rahu-Moon midpoint) event timing
- Jupiter 12-house cycle predictions
- Saturn 30-year cycle results
- Planet-house classical combination tables
"""

from datetime import datetime, timedelta

import swisseph as swe

from ..models import Chart, PlanetPosition
from .aspects import get_house_aspects
from .ashtakavarga import calculate_bav, calculate_sav, get_transit_score
from .bhrigu import (
    calculate_bhrigu_bindu, check_bb_activation,
    get_jupiter_cycle, get_saturn_cycle, get_planet_house_insight,
    PLANET_HOUSE_RESULTS,
)
from .constants import AYANAMSHA, RASHIS
from .dasha import calculate_dasha
from .shadbala import calculate_shadbala
from .strength import (
    EXALTATION, DEBILITATION, FRIENDS, ENEMIES,
    NEUTRALS, OWN_SIGNS, RASHI_LORDS, get_dignity,
)
from .vargas import calculate_all_vargas
from .vimshopaka import calculate_vimshopaka
from .yogas import detect_yogas

# ---------------------------------------------------------------------------
# House and Life-Area mappings
# ---------------------------------------------------------------------------
HOUSE_AREAS = {
    1:  {"primary": "self", "tags": {"health", "personality", "body"}},
    2:  {"primary": "wealth", "tags": {"family", "speech", "savings"}},
    3:  {"primary": "courage", "tags": {"siblings", "communication", "short_travel"}},
    4:  {"primary": "home", "tags": {"mother", "property", "vehicles", "education"}},
    5:  {"primary": "intellect", "tags": {"children", "creativity", "romance", "merit"}},
    6:  {"primary": "enemies", "tags": {"health_issues", "debts", "service", "competition"}},
    7:  {"primary": "marriage", "tags": {"partnerships", "business", "public"}},
    8:  {"primary": "longevity", "tags": {"obstacles", "sudden_events", "inheritance"}},
    9:  {"primary": "fortune", "tags": {"dharma", "father", "higher_education", "guru"}},
    10: {"primary": "career", "tags": {"profession", "status", "authority"}},
    11: {"primary": "gains", "tags": {"income", "friends", "desires_fulfilled"}},
    12: {"primary": "loss", "tags": {"expenses", "foreign", "spirituality"}},
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

# Varga charts relevant to each life area
AREA_VARGAS = {
    "Career": 10,       # D10 Dashamsha
    "Finance": 2,       # D2 Hora
    "Relationships": 9, # D9 Navamsa
    "Education": 24,    # D24 Chaturvimshamsha
    "Home/Property": 4, # D4 Chaturthamsha
    "Health": 1,        # D1 Rashi
    "Travel": 3,        # D3 Drekkana
    "Spirituality": 20, # D20 Vimshamsha
}

_POSITIVE_YOGAS = {
    "Gajakesari Yoga", "Budhaditya Yoga", "Hamsa Yoga", "Malavya Yoga",
    "Bhadra Yoga", "Ruchaka Yoga", "Shasha Yoga", "Dhana Yoga",
    "Raja Yoga", "Viparita Raja Yoga", "Guru-Mangal Yoga",
    "Chandra-Mangal Yoga",
}
_NEGATIVE_YOGAS = {"Kemadruma Yoga", "Manglik Dosha"}


# ===== Helper functions =====

def _mutual_relation(p1: str, p2: str) -> str:
    """Natural mutual relationship between two planets."""
    if p1 == p2:
        return "same"
    shadow = {"Rahu": "Saturn", "Ketu": "Mars"}
    p1 = shadow.get(p1, p1)
    p2 = shadow.get(p2, p2)
    if p1 == p2:
        return "friend"

    r1 = ("friend" if p2 in FRIENDS.get(p1, []) else
          "enemy" if p2 in ENEMIES.get(p1, []) else "neutral")
    r2 = ("friend" if p1 in FRIENDS.get(p2, []) else
          "enemy" if p1 in ENEMIES.get(p2, []) else "neutral")

    combo = {r1, r2}
    if combo == {"friend"}:
        return "best_friend"
    if combo == {"friend", "neutral"}:
        return "friend"
    if combo == {"neutral"}:
        return "neutral"
    if combo == {"enemy", "neutral"}:
        return "enemy"
    if combo == {"enemy"}:
        return "bitter_enemy"
    return "neutral"


def _get_house_lordships(lagna_rashi_idx: int) -> dict[str, list[int]]:
    lordships: dict[str, list[int]] = {}
    for h in range(1, 13):
        rashi = RASHIS[(lagna_rashi_idx + h - 1) % 12]
        lord = RASHI_LORDS[rashi]
        lordships.setdefault(lord, []).append(h)
    return lordships


def _functional_nature(houses: list[int]) -> str:
    kendra = {1, 4, 7, 10}
    trikona = {1, 5, 9}
    trik = {6, 8, 12}
    h_set = set(houses)
    has_kendra = bool(h_set & kendra)
    has_trikona = bool(h_set & trikona)
    has_trik = bool(h_set & trik)

    if has_trikona and has_kendra:
        return "yogakaraka"
    if has_trikona and not has_trik:
        return "benefic"
    if has_trik and not has_trikona and not has_kendra:
        return "malefic"
    if has_kendra and not has_trikona and not has_trik:
        return "kendradhipati"
    if has_trikona and has_trik:
        return "mixed"
    return "neutral"


def _get_transit_rashi(jd: float, planet_id: int) -> int:
    swe.set_sid_mode(AYANAMSHA)
    result, _ = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return int(result[0] / 30) % 12


def _sade_sati_phase(moon_rashi_idx: int, saturn_rashi_idx: int) -> str | None:
    diff = (saturn_rashi_idx - moon_rashi_idx) % 12
    if diff == 11:
        return "rising"
    elif diff == 0:
        return "peak"
    elif diff == 1:
        return "setting"
    return None


# ===== Strength: combined Shadbala + Vimshopaka =====

def _combined_strength(planet_name: str,
                       shadbala: dict, vimshopaka: dict) -> tuple[float, list[str]]:
    """Get 0-10 normalized strength from Shadbala + Vimshopaka.

    Shadbala ratio > 1.0 = meets BPHS requirement.
    Vimshopaka dasha_varga 0-20 scale.
    Combined and normalized to 0-10.
    """
    reasons = []

    # Shadbala component (0-10)
    sb = shadbala.get(planet_name)
    if sb:
        sb_score = min(10, sb.ratio * 5)  # ratio 2.0 → 10
        if sb.ratio >= 1.5:
            reasons.append(f"Shadbala strong ({sb.total:.0f}/{sb.required:.0f})")
        elif sb.ratio < 0.8:
            reasons.append(f"Shadbala weak ({sb.total:.0f}/{sb.required:.0f})")
    else:
        sb_score = 5.0

    # Vimshopaka component (0-10)
    vim = vimshopaka.get(planet_name)
    if vim:
        vim_score = vim.dasha_varga / 2  # 0-20 → 0-10
        if vim.dasha_varga >= 15:
            reasons.append(f"strong across vargas (Vim:{vim.dasha_varga:.1f}/20)")
        elif vim.dasha_varga <= 8:
            reasons.append(f"weak across vargas (Vim:{vim.dasha_varga:.1f}/20)")
    else:
        vim_score = 5.0

    # Weighted: 60% Shadbala, 40% Vimshopaka
    combined = sb_score * 0.6 + vim_score * 0.4
    return round(max(0, min(10, combined)), 1), reasons


# ===== Yoga activation =====

def _yoga_score_for_dasha(yogas: list[tuple[str, str]],
                          maha_lord: str, antar_lord: str | None) -> tuple[float, list[str]]:
    score = 0.0
    notes = []

    mahapurusha_map = {
        "Ruchaka Yoga": "Mars", "Bhadra Yoga": "Mercury",
        "Hamsa Yoga": "Jupiter", "Malavya Yoga": "Venus", "Shasha Yoga": "Saturn",
    }

    for yoga_name, yoga_desc in yogas:
        activated = False

        # Direct dasha lord check
        if maha_lord in yoga_desc or (antar_lord and antar_lord in yoga_desc):
            activated = True

        # Mahapurusha activation
        if yoga_name in mahapurusha_map:
            mp_planet = mahapurusha_map[yoga_name]
            if maha_lord == mp_planet or antar_lord == mp_planet:
                activated = True

        # Specific yoga checks
        if yoga_name == "Gajakesari Yoga" and maha_lord in ("Jupiter", "Moon"):
            activated = True
        elif yoga_name == "Budhaditya Yoga" and maha_lord in ("Sun", "Mercury"):
            activated = True
        elif yoga_name == "Chandra-Mangal Yoga" and maha_lord in ("Moon", "Mars"):
            activated = True

        if activated:
            if yoga_name in _POSITIVE_YOGAS:
                bonus = 2.0 if maha_lord in yoga_desc else 1.0
                score += bonus
                notes.append(f"{yoga_name} activated")
            elif yoga_name in _NEGATIVE_YOGAS:
                if yoga_name == "Kemadruma Yoga" and maha_lord == "Moon":
                    score -= 1.5
                    notes.append(f"{yoga_name} felt during Moon dasha")
                elif yoga_name == "Manglik Dosha" and maha_lord == "Mars":
                    notes.append(f"Manglik Dosha — Mars period affects relationships")

    return score, notes


# ===== Life area predictions with Bhrigu specifics =====

def _predict_life_areas(activated_houses: set, score: float,
                        maha_lord: str, antar_lord: str | None,
                        chart: Chart, house_aspects: dict,
                        lordships: dict, transit_notes: dict,
                        vargas: dict, shadbala: dict,
                        vimshopaka: dict) -> dict[str, dict]:
    """Generate chart-specific life area predictions using
    Parashari + Bhrigu techniques."""
    all_planets = {p.name: p for p in chart.planets}
    lagna_rashi_idx = int(chart.lagna.longitude / 30) % 12
    areas = {}

    for area_name, area_houses in LIFE_AREA_HOUSES.items():
        relevant = activated_houses & area_houses
        if not relevant:
            continue

        area_score = score * 0.4  # Base from overall
        details_parts = []

        for h in relevant:
            # House lord analysis
            h_rashi = RASHIS[(lagna_rashi_idx + h - 1) % 12]
            h_lord = RASHI_LORDS[h_rashi]
            h_lord_planet = all_planets.get(h_lord)

            if h_lord_planet:
                dignity = get_dignity(h_lord_planet)
                if dignity in ("Exalted", "Mooltrikona", "Own Sign"):
                    area_score += 1.5
                elif dignity == "Debilitated":
                    area_score -= 1.5
                elif dignity == "Enemy":
                    area_score -= 0.5

                # Bhrigu: specific result for house lord's placement
                insight = get_planet_house_insight(h_lord, h_lord_planet.house)
                if insight and h in (10, 7, 2, 5):  # Key houses
                    details_parts.append(f"H{h} lord {h_lord} in H{h_lord_planet.house}")

            # Planets in house
            for p in chart.planets:
                if p.house == h:
                    # Bhrigu planet-house specific result
                    ph_insight = get_planet_house_insight(p.name, h)
                    if ph_insight:
                        details_parts.append(ph_insight[:80])
                        # Score from Bhrigu: benefic placement = positive
                        if p.name in ("Jupiter", "Venus"):
                            area_score += 0.5
                        elif p.name in ("Saturn", "Rahu"):
                            area_score -= 0.3

            # Aspects
            for asp in house_aspects.get(h, []):
                if asp == "Jupiter":
                    area_score += 0.5
                elif asp == "Saturn":
                    area_score -= 0.3

        # Varga confirmation for this life area
        varga_div = AREA_VARGAS.get(area_name)
        if varga_div and varga_div in vargas:
            varga_chart = vargas[varga_div]
            # Check dasha lord's position in relevant varga
            for pos in varga_chart.positions:
                if pos.name == maha_lord:
                    varga_lord = RASHI_LORDS.get(pos.rashi, "")
                    # Good house in varga = confirmation
                    if pos.house in {1, 4, 5, 7, 9, 10, 11}:
                        area_score += 0.5
                        details_parts.append(
                            f"{maha_lord} in H{pos.house} of D{varga_div} confirms")
                    elif pos.house in {6, 8, 12}:
                        area_score -= 0.5
                        details_parts.append(
                            f"{maha_lord} in H{pos.house} of D{varga_div} — challenges")
                    break

        # Transit influence
        jup_cycle = transit_notes.get("jupiter_cycle", {})
        sat_cycle = transit_notes.get("saturn_cycle", {})

        if area_name == "Career":
            if jup_cycle.get("career"):
                details_parts.append(jup_cycle["career"])
                area_score += 1.0 if transit_notes.get("jupiter_good") else 0.3
            if sat_cycle.get("career"):
                details_parts.append(sat_cycle["career"])
        elif area_name == "Finance":
            if jup_cycle.get("finance"):
                details_parts.append(jup_cycle["finance"])
                area_score += 0.5
        elif area_name == "Relationships":
            if jup_cycle.get("relationships"):
                details_parts.append(jup_cycle["relationships"])
        elif area_name == "Health":
            if jup_cycle.get("health"):
                details_parts.append(jup_cycle["health"])
            if sat_cycle.get("health"):
                details_parts.append(sat_cycle["health"])
                area_score -= 0.5

        # Sade Sati impact
        if "sade_sati" in transit_notes:
            if area_name == "Health":
                area_score -= 1.0
            elif area_name in ("Career", "Relationships"):
                area_score -= 0.5

        # Determine outlook
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

        # Combine details — limit to most relevant
        combined_details = ". ".join(details_parts[:4]) if details_parts else ""

        areas[area_name] = {
            "outlook": outlook,
            "score": round(area_score, 1),
            "houses": sorted(relevant),
            "details": combined_details,
        }

    if not areas:
        areas["General"] = {
            "outlook": "favorable" if score >= 1 else ("mixed" if score >= -1 else "challenging"),
            "score": round(score, 1),
            "houses": [],
            "details": "Steady period. Focus on consistent effort.",
        }

    return areas


# ===== Main prediction engine =====

def generate_predictions(chart: Chart, start_year: int, end_year: int) -> tuple:
    """Generate predictions combining Parashari + Bhrigu techniques.

    Returns (predictions_list, bav, sav).
    """
    swe.set_ephe_path(None)
    swe.set_sid_mode(AYANAMSHA)

    lagna_rashi_idx = int(chart.lagna.longitude / 30) % 12
    moon = next(p for p in chart.planets if p.name == "Moon")
    moon_rashi_idx = int(moon.longitude / 30) % 12
    all_planets = {p.name: p for p in chart.planets}
    lordships = _get_house_lordships(lagna_rashi_idx)

    # ---- Pre-compute all chart data (once) ----
    dashas = calculate_dasha(chart)
    bav = calculate_bav(chart)
    sav = calculate_sav(bav)
    vargas = calculate_all_vargas(chart)
    vimshopaka = calculate_vimshopaka(chart, vargas)
    shadbala = calculate_shadbala(chart, vimshopaka)
    house_aspects = get_house_aspects(chart)
    yogas = detect_yogas(chart)
    bb = calculate_bhrigu_bindu(chart)

    predictions = []

    for year in range(start_year, end_year + 1):
        for half in range(2):
            if half == 0:
                period_start = datetime(year, 1, 1)
                period_end = datetime(year, 6, 30)
                period_label = f"Jan–Jun {year}"
            else:
                period_start = datetime(year, 7, 1)
                period_end = datetime(year, 12, 31)
                period_label = f"Jul–Dec {year}"

            mid_date = period_start + (period_end - period_start) / 2
            utc_hour = 12 - 5.5
            jd = swe.julday(mid_date.year, mid_date.month, mid_date.day, utc_hour)

            # ---- Find current dasha ----
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

            analysis = []
            score = 0.0
            transit_notes = {}

            # ======== PARASHARI ANALYSIS ========

            # 1. Mahadasha lord — Shadbala + Vimshopaka strength
            maha_houses = lordships.get(maha_lord, [])
            maha_nature = _functional_nature(maha_houses)
            maha_strength, maha_reasons = _combined_strength(
                maha_lord, shadbala, vimshopaka)
            maha_planet = all_planets.get(maha_lord)

            nature_scores = {
                "yogakaraka": 3.0, "benefic": 2.0, "kendradhipati": 0.5,
                "neutral": 0, "mixed": -0.5, "malefic": -2.0,
            }
            score += nature_scores.get(maha_nature, 0)

            if maha_strength >= 7:
                score += 2.0
            elif maha_strength >= 5:
                score += 0.5
            elif maha_strength <= 3:
                score -= 2.0
            elif maha_strength <= 4:
                score -= 1.0

            # Bhrigu: natal planet-house insight for dasha lord
            maha_natal_insight = ""
            if maha_planet:
                maha_natal_insight = get_planet_house_insight(
                    maha_lord, maha_planet.house)

            analysis.append(
                f"Mahadasha: {maha_lord} — {maha_nature} "
                f"(strength {maha_strength}/10"
                f"{', ' + ', '.join(maha_reasons) if maha_reasons else ''})"
            )
            for h in maha_houses:
                analysis.append(f"  rules H{h} ({HOUSE_AREAS[h]['primary']})")
            if maha_natal_insight:
                analysis.append(f"  Bhrigu: {maha_natal_insight[:100]}")

            # 2. Antardasha lord
            antar_info_houses = []
            if antar_lord:
                antar_houses = lordships.get(antar_lord, [])
                antar_nature = _functional_nature(antar_houses)
                antar_strength, antar_reasons = _combined_strength(
                    antar_lord, shadbala, vimshopaka)
                antar_info_houses = antar_houses

                # Mutual relationship
                relation = _mutual_relation(maha_lord, antar_lord)
                rel_scores = {
                    "same": 1.0, "best_friend": 1.5, "friend": 1.0,
                    "neutral": 0, "enemy": -1.0, "bitter_enemy": -1.5,
                }
                score += rel_scores.get(relation, 0)

                # Antardasha nature/strength (weighted less)
                score += nature_scores.get(antar_nature, 0) * 0.5
                if antar_strength >= 7:
                    score += 1.0
                elif antar_strength <= 3:
                    score -= 1.0

                analysis.append(
                    f"Antardasha: {antar_lord} — {antar_nature} "
                    f"(strength {antar_strength}/10), "
                    f"relation: {relation}"
                )

            # 3. Jupiter transit (Parashari + Bhrigu cycle)
            jup_rashi_idx = _get_transit_rashi(jd, swe.JUPITER)
            jup_from_moon = ((jup_rashi_idx - moon_rashi_idx) % 12) + 1
            jup_from_lagna = ((jup_rashi_idx - lagna_rashi_idx) % 12) + 1
            jup_bindus, _ = get_transit_score(bav, "Jupiter", jup_rashi_idx)
            jup_sav = sav[jup_rashi_idx]

            jup_good = {1, 2, 5, 7, 9, 11}
            jup_moon_good = jup_from_moon in jup_good
            jup_lagna_good = jup_from_lagna in jup_good

            # Bhrigu Jupiter cycle
            jup_cycle = get_jupiter_cycle(jup_from_lagna)
            transit_notes["jupiter_cycle"] = jup_cycle

            if jup_moon_good and jup_lagna_good:
                bonus = 2.5 if jup_bindus >= 5 else 1.5
                score += bonus
                transit_notes["jupiter_good"] = True
                analysis.append(
                    f"Jupiter transit H{jup_from_moon}/Moon, H{jup_from_lagna}/Lagna "
                    f"— strong support [BAV:{jup_bindus}/8, SAV:{jup_sav}]")
            elif jup_moon_good or jup_lagna_good:
                bonus = 1.5 if jup_bindus >= 5 else 0.5
                score += bonus
                transit_notes["jupiter_good"] = True
                analysis.append(
                    f"Jupiter transit H{jup_from_moon}/Moon, H{jup_from_lagna}/Lagna "
                    f"— partial support [BAV:{jup_bindus}/8]")
            else:
                penalty = 0 if jup_bindus >= 5 else -1.0
                score += penalty
                analysis.append(
                    f"Jupiter transit H{jup_from_moon}/Moon "
                    f"— limited support [BAV:{jup_bindus}/8]")

            if jup_cycle.get("summary"):
                analysis.append(f"  Bhrigu Jupiter: {jup_cycle['summary']}")

            # 4. Saturn transit & Sade Sati
            sat_rashi_idx = _get_transit_rashi(jd, swe.SATURN)
            sat_from_moon = ((sat_rashi_idx - moon_rashi_idx) % 12) + 1
            sat_from_lagna = ((sat_rashi_idx - lagna_rashi_idx) % 12) + 1
            sat_bindus, _ = get_transit_score(bav, "Saturn", sat_rashi_idx)

            # Bhrigu Saturn cycle
            sat_cycle = get_saturn_cycle(sat_from_lagna)
            transit_notes["saturn_cycle"] = sat_cycle

            sade_phase = _sade_sati_phase(moon_rashi_idx, sat_rashi_idx)
            if sade_phase:
                transit_notes["sade_sati"] = sade_phase
                base_penalty = {"rising": -1.5, "peak": -2.5, "setting": -1.0}[sade_phase]
                if sat_bindus >= 4:
                    base_penalty *= 0.6
                if "Jupiter" in house_aspects.get(moon.house, []):
                    base_penalty *= 0.5
                    analysis.append("Jupiter aspects Moon — Sade Sati reduced")
                score += base_penalty
                analysis.append(
                    f"SADE SATI — {sade_phase} phase "
                    f"[BAV:{sat_bindus}/8"
                    f"{', mitigated' if sat_bindus >= 4 else ''}]")
            else:
                sat_good = {3, 6, 11}
                if sat_from_moon in sat_good:
                    score += 1.5 if sat_bindus >= 4 else 0.5
                    analysis.append(
                        f"Saturn transit H{sat_from_moon}/Moon — favorable [BAV:{sat_bindus}/8]")
                elif sat_from_moon in {1, 4, 7, 8, 10, 12}:
                    penalty = -0.5 if sat_bindus >= 4 else -1.5
                    score += penalty
                    analysis.append(
                        f"Saturn transit H{sat_from_moon}/Moon — challenging [BAV:{sat_bindus}/8]")

            if sat_cycle.get("summary"):
                analysis.append(f"  Bhrigu Saturn: {sat_cycle['summary']}")

            # 5. Rahu/Ketu transit
            rahu_rashi_idx = _get_transit_rashi(jd, swe.MEAN_NODE)
            rahu_from_lagna = ((rahu_rashi_idx - lagna_rashi_idx) % 12) + 1
            rahu_from_moon = ((rahu_rashi_idx - moon_rashi_idx) % 12) + 1

            if rahu_from_lagna in {1, 2, 5, 7, 8, 9}:
                score -= 0.5
                analysis.append(
                    f"Rahu transit H{rahu_from_lagna}/Lagna "
                    f"— karmic disruptions in {HOUSE_AREAS.get(rahu_from_lagna, {}).get('primary', '')}")
            if rahu_from_moon in {1, 5, 7, 9}:
                score -= 0.3

            # ======== BHRIGU BINDU ACTIVATION ========
            bb_activations = check_bb_activation(bb, jd)
            bb_data = None
            if bb_activations:
                for act in bb_activations:
                    if act["effect"] == "positive":
                        score += 2.0
                    else:
                        score -= 1.0
                    analysis.append(f"⚡ {act['description']} (orb: {act['distance']}°)")
                bb_data = {
                    "activated_by": [a["planet"] for a in bb_activations],
                    "rashi": bb.rashi,
                    "degree": f"{bb.rashi_degree:.1f}°",
                    "house": bb.house,
                }

            # ======== YOGA ACTIVATION ========
            yoga_score, yoga_notes = _yoga_score_for_dasha(yogas, maha_lord, antar_lord)
            score += yoga_score
            if yoga_notes:
                analysis.extend(yoga_notes)

            # ======== DASHA SANDHI ========
            for lord, d_start, d_end, _ in dashas:
                days_to_end = (d_end - mid_date).days
                days_from_start = (mid_date - d_start).days
                if 0 < days_to_end < 90:
                    score -= 0.5
                    analysis.append("Dasha sandhi — transition approaching")
                    break
                elif 0 < days_from_start < 90:
                    score -= 0.5
                    analysis.append("Dasha sandhi — settling into new period")
                    break

            # ======== LIFE AREA PREDICTIONS ========
            activated_houses = set(maha_houses)
            if maha_planet:
                activated_houses.add(maha_planet.house)
            activated_houses |= set(antar_info_houses)
            if antar_lord and antar_lord in all_planets:
                activated_houses.add(all_planets[antar_lord].house)
            activated_houses.discard(0)

            life_areas = _predict_life_areas(
                activated_houses, score, maha_lord, antar_lord,
                chart, house_aspects, lordships, transit_notes,
                vargas, shadbala, vimshopaka)

            # ======== VARGA INSIGHTS ========
            varga_insights = {}
            for area_name, div in AREA_VARGAS.items():
                if div in vargas and area_name in life_areas:
                    vc = vargas[div]
                    for pos in vc.positions:
                        if pos.name == maha_lord:
                            varga_insights[f"{area_name}_D{div}"] = (
                                f"{maha_lord} in {pos.rashi} (H{pos.house}) in D{div}"
                            )
                            break

            # ======== OVERALL OUTLOOK ========
            if score >= 4:
                outlook = "Very Favorable"
            elif score >= 1.5:
                outlook = "Favorable"
            elif score >= -1.5:
                outlook = "Mixed"
            elif score >= -4:
                outlook = "Challenging"
            else:
                outlook = "Difficult"

            predictions.append({
                "period": period_label,
                "dasha": f"{maha_lord}-{antar_lord}" if antar_lord else maha_lord,
                "outlook": outlook,
                "score": round(score, 1),
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
                "varga_insights": varga_insights,
                "strength_method": "shadbala_vimshopaka",
            })

    swe.close()
    return predictions, bav, sav
