"""Prediction engine — classical Vedic approach.

Combines Vimshottari Dasha, Gochar (transits) with Ashtakavarga,
Navamsa confirmation, Yoga activation, Graha Drishti (aspects),
and contextual house-lord analysis for chart-specific predictions.

Classical references: Brihat Parashara Hora Shastra, Phaladeepika,
Uttara Kalamrita, Brihat Jataka.
"""

from datetime import datetime, timedelta

import swisseph as swe

from ..models import Chart, PlanetPosition
from .aspects import get_house_aspects, SPECIAL_ASPECTS
from .ashtakavarga import calculate_bav, calculate_sav, get_transit_score
from .constants import AYANAMSHA, RASHIS
from .dasha import calculate_dasha
from .navamsa import calculate_navamsa
from .strength import (
    DEBILITATION, EXALTATION, FRIENDS, ENEMIES, MOOLTRIKONA,
    NEUTRALS, OWN_SIGNS, RASHI_LORDS, get_dignity,
)
from .yogas import detect_yogas

# ---------------------------------------------------------------------------
# House significations — primary & secondary (Parasara / Uttara Kalamrita)
# ---------------------------------------------------------------------------
HOUSE_AREAS = {
    1:  {"primary": "self", "tags": {"health", "personality", "body"}},
    2:  {"primary": "wealth", "tags": {"family", "speech", "savings"}},
    3:  {"primary": "courage", "tags": {"siblings", "communication", "short_travel"}},
    4:  {"primary": "home", "tags": {"mother", "property", "vehicles", "education"}},
    5:  {"primary": "intellect", "tags": {"children", "creativity", "romance", "merit"}},
    6:  {"primary": "enemies", "tags": {"health_issues", "debts", "service", "competition"}},
    7:  {"primary": "marriage", "tags": {"partnerships", "business", "public"}},
    8:  {"primary": "longevity", "tags": {"obstacles", "sudden_events", "inheritance", "transformation"}},
    9:  {"primary": "fortune", "tags": {"dharma", "father", "higher_education", "guru", "long_travel"}},
    10: {"primary": "career", "tags": {"profession", "status", "authority", "public_image"}},
    11: {"primary": "gains", "tags": {"income", "friends", "desires_fulfilled"}},
    12: {"primary": "loss", "tags": {"expenses", "foreign", "spirituality", "liberation"}},
}

# Life-area groupings used for final report
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

# Yoga categories that modify prediction scores
_POSITIVE_YOGAS = {
    "Gajakesari Yoga", "Budhaditya Yoga", "Hamsa Yoga", "Malavya Yoga",
    "Bhadra Yoga", "Ruchaka Yoga", "Shasha Yoga", "Dhana Yoga",
    "Raja Yoga", "Viparita Raja Yoga", "Guru-Mangal Yoga",
    "Chandra-Mangal Yoga",
}
_NEGATIVE_YOGAS = {"Kemadruma Yoga", "Manglik Dosha"}

# Planet relationships for dasha lord compatibility
_NATURAL_RELATIONSHIP = {}  # Built lazily


# ===== Helper: mutual relationship between two planets =====

def _mutual_relation(p1: str, p2: str) -> str:
    """Classical 5-level relationship: best_friend / friend / neutral / enemy / bitter_enemy.

    Parasara: natural + temporary = 5-fold.
    Here we use natural relationship (sufficient for dasha compatibility).
    """
    if p1 == p2:
        return "same"
    if p1 in ("Rahu", "Ketu") or p2 in ("Rahu", "Ketu"):
        # Rahu acts like Saturn, Ketu like Mars for relationships
        shadow_map = {"Rahu": "Saturn", "Ketu": "Mars"}
        p1 = shadow_map.get(p1, p1)
        p2 = shadow_map.get(p2, p2)
        if p1 == p2:
            return "friend"

    p1_friends = set(FRIENDS.get(p1, []))
    p1_enemies = set(ENEMIES.get(p1, []))
    p2_friends = set(FRIENDS.get(p2, []))
    p2_enemies = set(ENEMIES.get(p2, []))

    # Mutual: both friend -> best_friend, friend+neutral -> friend, etc.
    r1 = "friend" if p2 in p1_friends else ("enemy" if p2 in p1_enemies else "neutral")
    r2 = "friend" if p1 in p2_friends else ("enemy" if p1 in p2_enemies else "neutral")

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
    if "friend" in combo and "enemy" in combo:
        return "neutral"
    return "neutral"


# ===== Functional nature of planets for a lagna =====

def _get_house_lordships(lagna_rashi_idx: int) -> dict[str, list[int]]:
    """Map planet -> list of houses it lords for given lagna."""
    lordships: dict[str, list[int]] = {}
    for h in range(1, 13):
        rashi = RASHIS[(lagna_rashi_idx + h - 1) % 12]
        lord = RASHI_LORDS[rashi]
        lordships.setdefault(lord, []).append(h)
    return lordships


def _functional_nature(planet: str, houses: list[int]) -> str:
    """Determine functional benefic/malefic status per Parasara."""
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
        return "kendradhipati"  # Context-dependent
    if has_trikona and has_trik:
        return "mixed"
    return "neutral"


# ===== Natal strength — multi-factor =====

def _natal_strength(planet: PlanetPosition, navamsa_data: list,
                    house_aspects: dict[int, list[str]]) -> tuple[float, list[str]]:
    """Comprehensive natal strength (0-10) combining dignity, house, navamsa, aspects.

    Classical Shadbala-inspired (simplified to key factors):
    1. Dignity in D1 (Sthana Bala)
    2. House placement (Bhava Bala)
    3. Navamsa dignity (Varga Bala — D9 confirmation)
    4. Aspects received (Drishti Bala)
    5. Retrograde status (Cheshta Bala)
    """
    score = 5.0
    reasons = []
    name = planet.name

    # 1. Dignity in D1
    dignity = get_dignity(planet)
    dignity_scores = {
        "Exalted": 3.0, "Mooltrikona": 2.5, "Own Sign": 2.0,
        "Friendly": 1.0, "Neutral": 0, "Enemy": -1.5, "Debilitated": -3.0,
    }
    ds = dignity_scores.get(dignity, 0)
    score += ds
    if ds >= 2.0:
        reasons.append(f"{dignity} in {planet.rashi}")
    elif ds <= -1.5:
        reasons.append(f"{dignity} in {planet.rashi}")

    # 2. House placement
    if planet.house in {1, 5, 9, 10}:
        score += 1.0
        reasons.append(f"strong house {planet.house}")
    elif planet.house in {4, 7}:
        score += 0.5
    elif planet.house in {6, 8, 12}:
        score -= 1.0
        reasons.append(f"trik house {planet.house}")

    # 3. Navamsa confirmation (Vargottama = same rashi in D1 and D9)
    for nav_name, nav_rashi, nav_house in navamsa_data:
        if nav_name == name:
            if nav_rashi == planet.rashi:
                score += 1.5
                reasons.append("Vargottama (D1=D9)")
            else:
                # Check D9 dignity
                nav_lord = RASHI_LORDS.get(nav_rashi, "")
                if nav_rashi in OWN_SIGNS.get(name, []):
                    score += 0.5
                    reasons.append(f"own sign in D9")
                elif name in EXALTATION and EXALTATION[name][0] == nav_rashi:
                    score += 1.0
                    reasons.append(f"exalted in D9")
                elif name in DEBILITATION and DEBILITATION[name][0] == nav_rashi:
                    score -= 1.0
                    reasons.append(f"debilitated in D9")
            break

    # 4. Aspects received
    aspecting = house_aspects.get(planet.house, [])
    for asp_planet in aspecting:
        if asp_planet in ("Jupiter",):
            score += 0.5
            reasons.append(f"Jupiter aspects H{planet.house}")
        elif asp_planet in ("Saturn",) and name not in ("Saturn",):
            score -= 0.3
        elif asp_planet in ("Mars",) and name not in ("Mars",):
            score -= 0.2

    # 5. Retrograde (Vakri) — extra cheshta bala in Vedic
    if planet.is_retrograde and name not in ("Rahu", "Ketu"):
        score += 0.5
        reasons.append("retrograde (extra strength)")

    return max(0.0, min(10.0, score)), reasons


# ===== Transit analysis =====

def _get_transit_rashi(jd: float, planet_id: int) -> int:
    """Get sidereal rashi index for a planet at given Julian day."""
    swe.set_sid_mode(AYANAMSHA)
    result, _ = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return int(result[0] / 30) % 12


def _sade_sati_phase(moon_rashi_idx: int, saturn_rashi_idx: int) -> str | None:
    """Check Sade Sati phase with classical names."""
    diff = (saturn_rashi_idx - moon_rashi_idx) % 12
    if diff == 11:
        return "rising"
    elif diff == 0:
        return "peak"
    elif diff == 1:
        return "setting"
    return None


# ===== Yoga activation during dasha =====

def _yoga_score_for_dasha(yogas: list[tuple[str, str]],
                          maha_lord: str, antar_lord: str | None,
                          chart: Chart) -> tuple[float, list[str]]:
    """Score yogas that activate during current dasha period.

    Classical principle: A yoga manifests when its participating
    planet runs as dasha or antardasha lord.
    """
    score = 0.0
    notes = []
    pm = {p.name: p for p in chart.planets}

    for yoga_name, yoga_desc in yogas:
        # Check if dasha lords participate in this yoga
        activated = False

        if yoga_name == "Gajakesari Yoga" and maha_lord in ("Jupiter", "Moon"):
            activated = True
        elif yoga_name == "Budhaditya Yoga" and maha_lord in ("Sun", "Mercury"):
            activated = True
        elif yoga_name == "Chandra-Mangal Yoga" and maha_lord in ("Moon", "Mars"):
            activated = True
        elif yoga_name == "Guru-Mangal Yoga" and maha_lord in ("Jupiter", "Mars"):
            activated = True
        elif "Yoga" in yoga_name and maha_lord in yoga_desc:
            activated = True
        elif yoga_name == "Raja Yoga" and (maha_lord in yoga_desc or
                                            (antar_lord and antar_lord in yoga_desc)):
            activated = True
        elif yoga_name == "Dhana Yoga" and (maha_lord in yoga_desc or
                                             (antar_lord and antar_lord in yoga_desc)):
            activated = True

        # Mahapurusha yogas activate when their planet runs dasha
        if yoga_name in ("Ruchaka Yoga", "Bhadra Yoga", "Hamsa Yoga",
                         "Malavya Yoga", "Shasha Yoga"):
            mp_planet = {"Ruchaka Yoga": "Mars", "Bhadra Yoga": "Mercury",
                         "Hamsa Yoga": "Jupiter", "Malavya Yoga": "Venus",
                         "Shasha Yoga": "Saturn"}
            if maha_lord == mp_planet.get(yoga_name) or antar_lord == mp_planet.get(yoga_name):
                activated = True

        if not activated:
            # Check antardasha lord too
            if antar_lord and antar_lord in yoga_desc:
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
                    notes.append(f"{yoga_name} — Mars dasha may affect relationships")

    return score, notes


# ===== Dasha lord analysis (deep) =====

def _analyze_dasha_lord(lord_name: str, chart: Chart, lordships: dict,
                        navamsa_data: list, house_aspects: dict,
                        all_planets: dict[str, PlanetPosition]) -> dict:
    """Deep analysis of a dasha lord using classical principles."""
    planet = all_planets.get(lord_name)
    if not planet:
        return {"strength": 5.0, "nature": "neutral", "houses": [],
                "reasons": [], "activated_tags": set()}

    houses = lordships.get(lord_name, [])
    nature = _functional_nature(lord_name, houses)
    strength, reasons = _natal_strength(planet, navamsa_data, house_aspects)

    # Collect life area tags activated by this lord
    activated_tags = set()
    for h in houses:
        activated_tags |= HOUSE_AREAS[h]["tags"]
    # Also tags from the house the planet sits in
    activated_tags |= HOUSE_AREAS[planet.house]["tags"]

    return {
        "strength": strength,
        "nature": nature,
        "houses": houses,
        "house_placed": planet.house,
        "rashi": planet.rashi,
        "dignity": get_dignity(planet),
        "reasons": reasons,
        "activated_tags": activated_tags,
    }


# ===== Life area predictions (chart-specific) =====

def _predict_life_areas(maha_info: dict, antar_info: dict | None,
                        score: float, chart: Chart,
                        house_aspects: dict[int, list[str]],
                        lordships: dict[str, list[int]],
                        transit_notes: dict) -> dict[str, dict]:
    """Generate chart-specific life area predictions.

    Instead of generic templates, this examines:
    - Which houses are activated (dasha lord's lordship + placement)
    - Strength of house lords
    - Planets occupying those houses
    - Aspects on those houses
    - Transit support/opposition
    """
    all_planets = {p.name: p for p in chart.planets}
    activated_houses = set(maha_info.get("houses", []))
    activated_houses.add(maha_info.get("house_placed", 0))
    if antar_info:
        activated_houses |= set(antar_info.get("houses", []))
        activated_houses.add(antar_info.get("house_placed", 0))
    activated_houses.discard(0)

    areas = {}

    for area_name, area_houses in LIFE_AREA_HOUSES.items():
        relevant = activated_houses & area_houses
        if not relevant:
            continue

        # Calculate area-specific strength
        area_score = score * 0.5  # Base from overall

        for h in relevant:
            # House lord strength
            h_rashi = RASHIS[(int(chart.lagna.longitude / 30) + h - 1) % 12]
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

            # Planets in this house (benefic/malefic)
            for p in chart.planets:
                if p.house == h:
                    if p.name in ("Jupiter", "Venus"):
                        area_score += 0.5
                    elif p.name in ("Saturn", "Rahu", "Ketu"):
                        area_score -= 0.3
                    if p.name == "Mars" and h in {7, 1, 4}:
                        area_score -= 0.5

            # Aspects on this house
            for asp in house_aspects.get(h, []):
                if asp == "Jupiter":
                    area_score += 0.5
                elif asp == "Saturn":
                    area_score -= 0.3

        # Transit influence on this area
        if area_name == "Career" and "jupiter_good" in transit_notes:
            area_score += 1.0
        if area_name == "Finance" and "jupiter_good" in transit_notes:
            area_score += 0.5
        if "sade_sati" in transit_notes:
            if area_name == "Health":
                area_score -= 1.0
            elif area_name in ("Career", "Relationships"):
                area_score -= 0.5

        # Determine outlook and specific advice
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
            "details": _area_detail(area_name, outlook, relevant,
                                    maha_info, antar_info, chart,
                                    house_aspects, all_planets),
        }

    # If no specific areas, give general
    if not areas:
        areas["General"] = {
            "outlook": "favorable" if score >= 1 else ("mixed" if score >= -1 else "challenging"),
            "score": round(score, 1),
            "houses": [],
            "details": _general_detail(score, maha_info),
        }

    return areas


def _area_detail(area: str, outlook: str, houses: set,
                 maha_info: dict, antar_info: dict | None,
                 chart: Chart, house_aspects: dict,
                 all_planets: dict) -> str:
    """Generate chart-specific detail for a life area."""
    maha_lord = maha_info.get("rashi", "")
    maha_nature = maha_info.get("nature", "neutral")
    maha_strength = maha_info.get("strength", 5.0)
    maha_dignity = maha_info.get("dignity", "")

    parts = []

    # Dasha lord context
    if maha_nature == "yogakaraka":
        parts.append("Dasha lord is Yogakaraka — strongly supportive period")
    elif maha_nature == "benefic" and maha_strength >= 6:
        parts.append("Dasha lord is functionally benefic and strong")
    elif maha_nature == "malefic":
        parts.append("Dasha lord is a functional malefic — caution advised")

    # Dignity context
    if maha_dignity == "Exalted":
        parts.append("Exalted dasha lord amplifies positive results")
    elif maha_dignity == "Debilitated":
        parts.append("Debilitated dasha lord weakens outcomes")

    # House-specific observations
    for h in sorted(houses):
        occupants = [p.name for p in chart.planets if p.house == h]
        aspectors = house_aspects.get(h, [])

        if occupants:
            parts.append(f"House {h}: {', '.join(occupants)} present")
        if "Jupiter" in aspectors and h not in [p.house for p in chart.planets if p.name == "Jupiter"]:
            parts.append(f"Jupiter's aspect on H{h} protects and expands")
        if "Saturn" in aspectors and "Saturn" not in occupants:
            parts.append(f"Saturn's aspect on H{h} brings delays but structure")

    # Area-specific classical insights
    if area == "Career":
        if outlook in ("very_favorable", "favorable"):
            parts.append("Professional growth and recognition likely")
        elif outlook == "challenging":
            parts.append("Workplace challenges — patience and diplomacy needed")

    elif area == "Finance":
        if outlook in ("very_favorable", "favorable"):
            parts.append("Financial gains expected — good for investments")
        elif outlook in ("challenging", "difficult"):
            parts.append("Financial caution — avoid speculative risks")

    elif area == "Relationships":
        if outlook in ("very_favorable", "favorable"):
            parts.append("Harmonious period for partnerships")
        elif outlook in ("challenging", "difficult"):
            parts.append("Relationship tensions possible — practice understanding")

    elif area == "Health":
        if outlook in ("challenging", "difficult"):
            parts.append("Health needs attention — don't ignore minor symptoms")
        else:
            parts.append("Good vitality — maintain healthy routines")

    return ". ".join(parts) if parts else ""


def _general_detail(score: float, maha_info: dict) -> str:
    if score >= 2:
        return "Overall positive period. Good energy for new initiatives."
    elif score >= 0:
        return "Moderate period. Steady progress with consistent effort."
    elif score >= -2:
        return "Mixed results. Focus on essentials, avoid overcommitment."
    else:
        return "Challenging period. Patience and inner strength needed."


# ===== Main prediction engine =====

def generate_predictions(chart: Chart, start_year: int, end_year: int) -> tuple:
    """Generate predictions combining all classical techniques.

    Returns (predictions_list, bav, sav).
    """
    swe.set_ephe_path(None)
    swe.set_sid_mode(AYANAMSHA)

    lagna_rashi_idx = int(chart.lagna.longitude / 30) % 12
    moon = next(p for p in chart.planets if p.name == "Moon")
    moon_rashi_idx = int(moon.longitude / 30) % 12

    all_planets = {p.name: p for p in chart.planets}
    lordships = _get_house_lordships(lagna_rashi_idx)
    dashas = calculate_dasha(chart)

    # Ashtakavarga
    bav = calculate_bav(chart)
    sav = calculate_sav(bav)

    # Navamsa
    navamsa_data = calculate_navamsa(chart)

    # Aspects
    house_aspects = get_house_aspects(chart)

    # Yogas (detected once, activated per period)
    yogas = detect_yogas(chart)

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
            utc_hour = 12 - 5.5  # noon IST
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

            # ---- 1. Mahadasha lord deep analysis ----
            maha_info = _analyze_dasha_lord(
                maha_lord, chart, lordships, navamsa_data,
                house_aspects, all_planets)

            nature = maha_info["nature"]
            strength = maha_info["strength"]

            # Score from functional nature
            nature_scores = {
                "yogakaraka": 3.0, "benefic": 2.0, "kendradhipati": 0.5,
                "neutral": 0, "mixed": -0.5, "malefic": -2.0,
            }
            score += nature_scores.get(nature, 0)

            # Score from natal strength
            if strength >= 7:
                score += 2.0
            elif strength >= 5:
                score += 0.5
            elif strength <= 3:
                score -= 2.0
            elif strength <= 4:
                score -= 1.0

            analysis.append(
                f"Mahadasha: {maha_lord} — {nature} "
                f"(strength {strength:.1f}/10"
                f"{', ' + ', '.join(maha_info['reasons']) if maha_info['reasons'] else ''})"
            )
            for h in maha_info["houses"]:
                analysis.append(
                    f"  rules H{h} ({HOUSE_AREAS[h]['primary']})")

            # ---- 2. Antardasha lord analysis ----
            antar_info = None
            if antar_lord:
                antar_info = _analyze_dasha_lord(
                    antar_lord, chart, lordships, navamsa_data,
                    house_aspects, all_planets)

                # Maha-Antar lord mutual relationship
                relation = _mutual_relation(maha_lord, antar_lord)
                relation_scores = {
                    "same": 1.0, "best_friend": 1.5, "friend": 1.0,
                    "neutral": 0, "enemy": -1.0, "bitter_enemy": -1.5,
                }
                rel_score = relation_scores.get(relation, 0)
                score += rel_score

                a_nature = antar_info["nature"]
                a_strength = antar_info["strength"]

                # Antardasha nature/strength (weighted less than mahadasha)
                a_nature_score = nature_scores.get(a_nature, 0) * 0.5
                score += a_nature_score

                if a_strength >= 7:
                    score += 1.0
                elif a_strength <= 3:
                    score -= 1.0

                analysis.append(
                    f"Antardasha: {antar_lord} — {a_nature} "
                    f"(strength {a_strength:.1f}/10), "
                    f"relation with {maha_lord}: {relation}"
                )

            # ---- 3. Jupiter transit with Ashtakavarga ----
            transit_notes = {}

            jup_rashi_idx = _get_transit_rashi(jd, swe.JUPITER)
            jup_from_moon = ((jup_rashi_idx - moon_rashi_idx) % 12) + 1
            jup_from_lagna = ((jup_rashi_idx - lagna_rashi_idx) % 12) + 1
            jup_bindus, jup_quality = get_transit_score(bav, "Jupiter", jup_rashi_idx)
            jup_sav = sav[jup_rashi_idx]

            jup_good_moon = {1, 2, 5, 7, 9, 11}
            jup_good_lagna = {1, 2, 5, 7, 9, 11}

            jup_moon_good = jup_from_moon in jup_good_moon
            jup_lagna_good = jup_from_lagna in jup_good_lagna

            if jup_moon_good and jup_lagna_good:
                bonus = 2.5 if jup_bindus >= 5 else 1.5
                score += bonus
                transit_notes["jupiter_good"] = True
                analysis.append(
                    f"Jupiter transit H{jup_from_moon}/Moon, H{jup_from_lagna}/Lagna "
                    f"({RASHIS[jup_rashi_idx]}) — strong support "
                    f"[BAV:{jup_bindus}/8, SAV:{jup_sav}]")
            elif jup_moon_good or jup_lagna_good:
                bonus = 1.5 if jup_bindus >= 5 else 0.5
                score += bonus
                transit_notes["jupiter_good"] = True
                analysis.append(
                    f"Jupiter transit H{jup_from_moon}/Moon, H{jup_from_lagna}/Lagna "
                    f"({RASHIS[jup_rashi_idx]}) — partial support "
                    f"[BAV:{jup_bindus}/8]")
            else:
                penalty = 0 if jup_bindus >= 5 else -1.0
                score += penalty
                if jup_bindus >= 5:
                    analysis.append(
                        f"Jupiter transit H{jup_from_moon}/Moon "
                        f"({RASHIS[jup_rashi_idx]}) — weak house but strong BAV [{jup_bindus}/8]")
                else:
                    analysis.append(
                        f"Jupiter transit H{jup_from_moon}/Moon "
                        f"({RASHIS[jup_rashi_idx]}) — limited support "
                        f"[BAV:{jup_bindus}/8, SAV:{jup_sav}]")

            # ---- 4. Saturn transit & Sade Sati ----
            sat_rashi_idx = _get_transit_rashi(jd, swe.SATURN)
            sat_from_moon = ((sat_rashi_idx - moon_rashi_idx) % 12) + 1
            sat_bindus, sat_quality = get_transit_score(bav, "Saturn", sat_rashi_idx)
            sat_sav = sav[sat_rashi_idx]

            sade_phase = _sade_sati_phase(moon_rashi_idx, sat_rashi_idx)
            if sade_phase:
                transit_notes["sade_sati"] = sade_phase
                # Nuanced: peak is worst, rising/setting are milder
                # Good BAV reduces impact, Jupiter aspect can cancel
                base_penalty = {"rising": -1.5, "peak": -2.5, "setting": -1.0}[sade_phase]
                if sat_bindus >= 4:
                    base_penalty *= 0.6  # Good BAV mitigates
                # Jupiter aspecting Moon or Saturn reduces Sade Sati
                if "Jupiter" in house_aspects.get(moon.house, []):
                    base_penalty *= 0.5
                    analysis.append("Jupiter's aspect on Moon reduces Sade Sati impact")
                score += base_penalty
                analysis.append(
                    f"SADE SATI — {sade_phase} phase "
                    f"[BAV:{sat_bindus}/8"
                    f"{', mitigated' if sat_bindus >= 4 else ''}]")
            else:
                sat_good = {3, 6, 11}
                sat_bad = {1, 4, 7, 8, 10, 12}
                if sat_from_moon in sat_good:
                    bonus = 1.5 if sat_bindus >= 4 else 0.5
                    score += bonus
                    analysis.append(
                        f"Saturn transit H{sat_from_moon}/Moon "
                        f"— favorable [BAV:{sat_bindus}/8]")
                elif sat_from_moon in sat_bad:
                    penalty = -0.5 if sat_bindus >= 4 else -1.5
                    score += penalty
                    analysis.append(
                        f"Saturn transit H{sat_from_moon}/Moon "
                        f"— challenging [BAV:{sat_bindus}/8"
                        f"{', mitigated by good bindus' if sat_bindus >= 4 else ''}]")

            # ---- 5. Rahu/Ketu transit ----
            rahu_rashi_idx = _get_transit_rashi(jd, swe.MEAN_NODE)
            rahu_from_lagna = ((rahu_rashi_idx - lagna_rashi_idx) % 12) + 1
            rahu_from_moon = ((rahu_rashi_idx - moon_rashi_idx) % 12) + 1
            ketu_from_lagna = ((rahu_from_lagna + 5) % 12) + 1  # 7th from Rahu

            rahu_sensitive = {1, 2, 5, 7, 8, 9}
            if rahu_from_lagna in rahu_sensitive:
                score -= 0.5
                analysis.append(
                    f"Rahu transit H{rahu_from_lagna}/Lagna "
                    f"— karmic disruptions in {HOUSE_AREAS.get(rahu_from_lagna, {}).get('primary', '')}")
            if rahu_from_moon in {1, 5, 7, 9}:
                score -= 0.3
                analysis.append(
                    f"Rahu transit H{rahu_from_moon}/Moon — mental restlessness")

            # ---- 6. Yoga activation ----
            yoga_score, yoga_notes = _yoga_score_for_dasha(
                yogas, maha_lord, antar_lord, chart)
            score += yoga_score
            if yoga_notes:
                analysis.extend(yoga_notes)

            # ---- 7. Dasha sandhi check ----
            # Transition between dashas is turbulent
            for lord, d_start, d_end, _ in dashas:
                days_to_end = (d_end - mid_date).days
                days_from_start = (mid_date - d_start).days
                if 0 < days_to_end < 90:
                    score -= 0.5
                    analysis.append(f"Dasha sandhi approaching — transition period")
                    break
                elif 0 < days_from_start < 90:
                    score -= 0.5
                    analysis.append(f"Dasha sandhi — settling into new period")
                    break

            # ---- Generate life area predictions ----
            life_areas = _predict_life_areas(
                maha_info, antar_info, score, chart,
                house_aspects, lordships, transit_notes)

            # ---- Overall outlook ----
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
            })

    swe.close()
    return predictions, bav, sav
