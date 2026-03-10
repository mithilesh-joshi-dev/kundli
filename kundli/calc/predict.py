"""Prediction engine combining Dasha, Transit, and natal chart analysis."""

from datetime import datetime, timedelta, timezone

import swisseph as swe

from ..models import Chart, PlanetPosition
from .ashtakavarga import calculate_bav, calculate_sav, get_transit_score
from .constants import AYANAMSHA, NAKSHATRAS, RASHIS
from .dasha import calculate_dasha
from .strength import (
    DEBILITATION, EXALTATION, FRIENDS, ENEMIES, MOOLTRIKONA,
    OWN_SIGNS, RASHI_LORDS, get_dignity,
)


# Functional nature of planets for each lagna
# Benefic = lords of kendra (1,4,7,10) and trikona (1,5,9)
# Malefic = lords of trik houses (6,8,12) and maraka (2,7)
# Neutral = lords of 3,11
def _get_house_lordships(lagna_rashi_idx: int) -> dict[str, list[int]]:
    """Map planet -> list of houses it lords for given lagna."""
    lordships: dict[str, list[int]] = {}
    for h in range(1, 13):
        rashi = RASHIS[(lagna_rashi_idx + h - 1) % 12]
        lord = RASHI_LORDS[rashi]
        lordships.setdefault(lord, []).append(h)
    return lordships


def _functional_nature(planet: str, houses: list[int]) -> str:
    """Determine if planet is functionally benefic, malefic, or neutral."""
    kendra = {1, 4, 7, 10}
    trikona = {1, 5, 9}
    trik = {6, 8, 12}
    maraka = {2, 7}

    has_kendra = bool(set(houses) & kendra)
    has_trikona = bool(set(houses) & trikona)
    has_trik = bool(set(houses) & trik)

    if has_trikona and not has_trik:
        return "benefic"
    if has_trikona and has_kendra:
        return "yogakaraka"
    if has_trik and not has_trikona and not has_kendra:
        return "malefic"
    if has_kendra and not has_trikona and not has_trik:
        return "neutral"  # Kendradhipati — context dependent
    if has_trikona and has_trik:
        return "mixed"
    return "neutral"


def _planet_strength_score(planet: PlanetPosition) -> tuple[float, list[str]]:
    """Score a planet's natal strength (0-10) with reasons."""
    score = 5.0  # Base
    reasons = []

    dignity = get_dignity(planet)
    if dignity == "Exalted":
        score += 3.0
        reasons.append("Exalted (very strong)")
    elif dignity == "Mooltrikona":
        score += 2.5
        reasons.append("Mooltrikona (strong)")
    elif dignity == "Own Sign":
        score += 2.0
        reasons.append("Own sign (strong)")
    elif dignity == "Friendly":
        score += 1.0
        reasons.append("Friendly sign")
    elif dignity == "Neutral":
        pass
    elif dignity == "Enemy":
        score -= 1.5
        reasons.append("Enemy sign (weakened)")
    elif dignity == "Debilitated":
        score -= 3.0
        reasons.append("Debilitated (very weak)")

    if planet.is_retrograde and planet.name not in ("Rahu", "Ketu"):
        score += 0.5
        reasons.append("Retrograde (extra strength in Vedic)")

    # House placement
    good_houses = {1, 2, 4, 5, 7, 9, 10, 11}
    bad_houses = {6, 8, 12}
    if planet.house in {1, 5, 9, 10}:
        score += 1.0
        reasons.append(f"Well placed in house {planet.house}")
    elif planet.house in {6, 8, 12}:
        score -= 1.0
        reasons.append(f"Placed in trik house {planet.house}")

    return max(0, min(10, score)), reasons


def _sade_sati_status(moon_rashi_idx: int, saturn_rashi_idx: int) -> str | None:
    """Check Sade Sati phase."""
    diff = (saturn_rashi_idx - moon_rashi_idx) % 12
    if diff == 11:  # 12th from Moon
        return "Rising (1st phase) — Saturn in 12th from Moon"
    elif diff == 0:  # Over Moon
        return "Peak (2nd phase) — Saturn over Moon sign"
    elif diff == 1:  # 2nd from Moon
        return "Setting (3rd phase) — Saturn in 2nd from Moon"
    return None


def _get_current_transit_rashi(jd: float, planet_id: int) -> int:
    """Get sidereal rashi index for a planet at given Julian day."""
    swe.set_sid_mode(AYANAMSHA)
    result, _ = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return int(result[0] / 30) % 12


# Life area significations for each house
HOUSE_SIGNIFICATIONS = {
    1: "self, health, personality, new beginnings",
    2: "wealth, family, speech, food",
    3: "siblings, courage, short travels, communication",
    4: "mother, home, property, vehicles, education",
    5: "children, creativity, romance, intelligence, past merit",
    6: "enemies, diseases, debts, service, competition",
    7: "marriage, partnerships, business, public dealings",
    8: "longevity, obstacles, sudden events, inheritance, transformation",
    9: "luck, dharma, father, higher education, long travels, guru",
    10: "career, profession, status, authority, public image",
    11: "gains, income, social circle, fulfillment of desires",
    12: "losses, expenses, foreign lands, spirituality, liberation",
}


def generate_predictions(chart: Chart, start_year: int, end_year: int) -> list[dict]:
    """Generate predictions combining dasha, transit, and natal strength.

    Returns list of prediction dicts with period, analysis, and advice.
    """
    swe.set_ephe_path(None)
    swe.set_sid_mode(AYANAMSHA)

    lagna_rashi_idx = int(chart.lagna.longitude / 30) % 12
    moon = next(p for p in chart.planets if p.name == "Moon")
    moon_rashi_idx = int(moon.longitude / 30) % 12

    lordships = _get_house_lordships(lagna_rashi_idx)
    dashas = calculate_dasha(chart)

    # Ashtakavarga
    bav = calculate_bav(chart)
    sav = calculate_sav(bav)

    predictions = []

    # Analyze each year
    for year in range(start_year, end_year + 1):
        for half in range(2):  # H1 and H2
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

            # Current dasha
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
            areas = []
            score = 0  # -10 to +10 overall

            # 1. Mahadasha lord analysis
            maha_planet = next((p for p in chart.planets if p.name == maha_lord), None)
            if maha_planet:
                strength, reasons = _planet_strength_score(maha_planet)
                maha_houses = lordships.get(maha_lord, [])
                nature = _functional_nature(maha_lord, maha_houses)
                house_areas = [HOUSE_SIGNIFICATIONS.get(h, "") for h in maha_houses]

                if nature in ("benefic", "yogakaraka"):
                    score += 2
                elif nature == "malefic":
                    score -= 2

                if strength >= 7:
                    score += 2
                    analysis.append(f"Mahadasha lord {maha_lord} is strong ({', '.join(reasons)})")
                elif strength <= 3:
                    score -= 2
                    analysis.append(f"Mahadasha lord {maha_lord} is weak ({', '.join(reasons)})")
                else:
                    analysis.append(f"Mahadasha lord {maha_lord} has moderate strength")

                analysis.append(f"  {maha_lord} rules house(s) {', '.join(str(h) for h in maha_houses)} "
                               f"({nature}) — {'; '.join(house_areas)}")
                areas.extend(maha_houses)

            # 2. Antardasha lord analysis
            if antar_lord and antar_lord != maha_lord:
                antar_planet = next((p for p in chart.planets if p.name == antar_lord), None)
                if antar_planet:
                    a_strength, a_reasons = _planet_strength_score(antar_planet)
                    antar_houses = lordships.get(antar_lord, [])
                    a_nature = _functional_nature(antar_lord, antar_houses)

                    if a_nature in ("benefic", "yogakaraka") and a_strength >= 6:
                        score += 1
                    elif a_nature == "malefic" and a_strength <= 4:
                        score -= 1

                    analysis.append(f"Antardasha lord {antar_lord} in {antar_planet.rashi} "
                                   f"(house {antar_planet.house}, {a_nature})")
                    areas.extend(antar_houses)

            # 3. Jupiter transit (with Ashtakavarga)
            jup_rashi_idx = _get_current_transit_rashi(jd, swe.JUPITER)
            jup_house_from_moon = ((jup_rashi_idx - moon_rashi_idx) % 12) + 1
            jup_bindus, jup_quality = get_transit_score(bav, "Jupiter", jup_rashi_idx)
            jup_sav = sav[jup_rashi_idx]

            jup_good = {1, 2, 5, 7, 9, 11}
            if jup_house_from_moon in jup_good:
                jup_bonus = 2 if jup_bindus >= 5 else 1
                score += jup_bonus
                analysis.append(f"Jupiter transiting H{jup_house_from_moon} from Moon ({RASHIS[jup_rashi_idx]}) "
                               f"— favorable [BAV:{jup_bindus}/8, SAV:{jup_sav}]")
            else:
                jup_penalty = 0 if jup_bindus >= 5 else -1
                score += jup_penalty
                if jup_bindus >= 5:
                    analysis.append(f"Jupiter transiting H{jup_house_from_moon} from Moon ({RASHIS[jup_rashi_idx]}) "
                                   f"— house is difficult but strong BAV [{jup_bindus}/8] mitigates")
                else:
                    analysis.append(f"Jupiter transiting H{jup_house_from_moon} from Moon ({RASHIS[jup_rashi_idx]}) "
                                   f"— challenging [BAV:{jup_bindus}/8, SAV:{jup_sav}]")

            # 4. Saturn transit & Sade Sati (with Ashtakavarga)
            sat_rashi_idx = _get_current_transit_rashi(jd, swe.SATURN)
            sat_house_from_moon = ((sat_rashi_idx - moon_rashi_idx) % 12) + 1
            sat_bindus, sat_quality = get_transit_score(bav, "Saturn", sat_rashi_idx)
            sat_sav = sav[sat_rashi_idx]

            sade_sati = _sade_sati_status(moon_rashi_idx, sat_rashi_idx)
            if sade_sati:
                sade_penalty = -1 if sat_bindus >= 4 else -2
                score += sade_penalty
                analysis.append(f"SADE SATI {sade_sati} [BAV:{sat_bindus}/8"
                               f"{' — reduced impact due to good bindus' if sat_bindus >= 4 else ''}]")
            else:
                sat_good = {3, 6, 11}
                if sat_house_from_moon in sat_good:
                    sat_bonus = 2 if sat_bindus >= 4 else 1
                    score += sat_bonus
                    analysis.append(f"Saturn transiting H{sat_house_from_moon} from Moon "
                                   f"— favorable [BAV:{sat_bindus}/8, SAV:{sat_sav}]")
                elif sat_house_from_moon in {1, 4, 7, 8, 10, 12}:
                    sat_penalty = 0 if sat_bindus >= 4 else -1
                    score += sat_penalty
                    if sat_bindus >= 4:
                        analysis.append(f"Saturn transiting H{sat_house_from_moon} from Moon "
                                       f"— stressful house but good BAV [{sat_bindus}/8] mitigates")
                    else:
                        analysis.append(f"Saturn transiting H{sat_house_from_moon} from Moon "
                                       f"— stressful [BAV:{sat_bindus}/8, SAV:{sat_sav}]")

            # 5. Rahu/Ketu transit
            rahu_rashi_idx = _get_current_transit_rashi(jd, swe.MEAN_NODE)
            rahu_house_from_lagna = ((rahu_rashi_idx - lagna_rashi_idx) % 12) + 1
            if rahu_house_from_lagna in {1, 5, 7, 9}:
                analysis.append(f"Rahu transiting H{rahu_house_from_lagna} from Lagna — karmic disruptions in "
                               f"{HOUSE_SIGNIFICATIONS.get(rahu_house_from_lagna, '')}")

            # Generate life area predictions
            life_areas = _predict_life_areas(areas, score, maha_lord, antar_lord, chart)

            # Overall rating
            if score >= 3:
                outlook = "Very Favorable"
            elif score >= 1:
                outlook = "Favorable"
            elif score >= -1:
                outlook = "Mixed"
            elif score >= -3:
                outlook = "Challenging"
            else:
                outlook = "Difficult"

            predictions.append({
                "period": period_label,
                "dasha": f"{maha_lord}-{antar_lord}" if antar_lord else maha_lord,
                "outlook": outlook,
                "score": score,
                "analysis": analysis,
                "life_areas": life_areas,
            })

    swe.close()
    return predictions, bav, sav


def _predict_life_areas(houses: list[int], score: int,
                        maha_lord: str, antar_lord: str | None,
                        chart: Chart) -> dict[str, str]:
    """Generate specific life area predictions based on activated houses."""
    areas = {}
    house_set = set(houses)

    # Career (10, 6, 2)
    if house_set & {10, 6, 2, 11}:
        if score >= 2:
            areas["Career"] = "Growth and recognition likely. Good period for professional advancement."
        elif score >= 0:
            areas["Career"] = "Steady period. Maintain consistency, avoid major risks."
        else:
            areas["Career"] = "Challenges at work possible. Stay patient and avoid conflicts."

    # Finances (2, 11, 5)
    if house_set & {2, 11, 5}:
        if score >= 2:
            areas["Finance"] = "Financial gains expected. Good for investments and savings."
        elif score >= 0:
            areas["Finance"] = "Moderate financial flow. Avoid unnecessary expenses."
        else:
            areas["Finance"] = "Financial caution advised. Unexpected expenses possible."

    # Relationships (7, 1, 5)
    if house_set & {7, 1, 5}:
        if score >= 2:
            areas["Relationships"] = "Harmonious period for partnerships and love."
        elif score >= 0:
            areas["Relationships"] = "Stable relationships. Communication is key."
        else:
            areas["Relationships"] = "Tensions in relationships possible. Practice patience."

    # Health (1, 6, 8)
    if house_set & {1, 6, 8}:
        if score >= 1:
            areas["Health"] = "Good vitality. Maintain healthy routines."
        else:
            areas["Health"] = "Health needs attention. Don't ignore minor issues."

    # Education/Wisdom (4, 5, 9)
    if house_set & {4, 5, 9}:
        if score >= 1:
            areas["Education"] = "Favorable for learning, exams, and spiritual growth."
        else:
            areas["Education"] = "Focus and discipline needed in studies."

    # Property/Home (4)
    if 4 in house_set:
        if score >= 1:
            areas["Home/Property"] = "Good period for property matters and domestic happiness."
        else:
            areas["Home/Property"] = "Domestic tensions or property issues possible."

    # Travel (3, 9, 12)
    if house_set & {3, 9, 12}:
        if score >= 0:
            areas["Travel"] = "Travel opportunities likely. Beneficial journeys."
        else:
            areas["Travel"] = "Travel may cause stress. Plan carefully."

    # If no specific areas, give general
    if not areas:
        if score >= 1:
            areas["General"] = "Overall positive period. Good energy for new initiatives."
        elif score >= -1:
            areas["General"] = "Mixed period. Take things one step at a time."
        else:
            areas["General"] = "Patience needed. Focus on self-care and inner strength."

    return areas
