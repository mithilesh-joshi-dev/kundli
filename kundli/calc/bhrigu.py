"""Bhrigu Samhita techniques — Bhrigu Bindu, Jupiter/Saturn cycles.

Implements three key Bhrigu prediction methods:
1. Bhrigu Bindu — Rahu-Moon midpoint for event timing
2. Jupiter 12-house cycle — year-by-year event predictions
3. Saturn 30-year cycle — karmic lesson predictions
"""

import swisseph as swe

from ..models import BhriguBindu, Chart
from .constants import AYANAMSHA, RASHIS
from .strength import RASHI_LORDS


# ===== Bhrigu Bindu =====

def _midpoint(lon1: float, lon2: float) -> float:
    """Calculate midpoint of two longitudes on a 360° circle (shorter arc)."""
    diff = (lon2 - lon1) % 360
    if diff > 180:
        mid = (lon1 + diff / 2 + 180) % 360
    else:
        mid = (lon1 + diff / 2) % 360
    return mid


def calculate_bhrigu_bindu(chart: Chart) -> BhriguBindu:
    """Calculate Bhrigu Bindu — midpoint of Rahu and Moon.

    The BB is a highly sensitive degree. When Jupiter or Saturn
    transit over it (within 3° orb), significant life events occur.
    Jupiter = positive events, Saturn = karmic challenges.
    """
    rahu = next(p for p in chart.planets if p.name == "Rahu")
    moon = next(p for p in chart.planets if p.name == "Moon")

    bb_lon = _midpoint(rahu.longitude, moon.longitude)
    rashi_idx = int(bb_lon / 30) % 12
    rashi = RASHIS[rashi_idx]
    rashi_deg = round(bb_lon % 30, 2)

    lagna_idx = int(chart.lagna.longitude / 30) % 12
    house = ((rashi_idx - lagna_idx) % 12) + 1

    return BhriguBindu(
        longitude=round(bb_lon, 4),
        rashi=rashi,
        rashi_degree=rashi_deg,
        house=house,
    )


def check_bb_activation(bb: BhriguBindu, jd: float,
                        orb: float = 3.0) -> list[dict]:
    """Check if Jupiter or Saturn is transiting over Bhrigu Bindu.

    Args:
        bb: Calculated Bhrigu Bindu.
        jd: Julian day for the transit check.
        orb: Degrees of orb for activation.

    Returns:
        List of activation dicts with planet, exact_distance, effect.
    """
    swe.set_sid_mode(AYANAMSHA)
    activations = []

    for planet_name, planet_id in [("Jupiter", swe.JUPITER), ("Saturn", swe.SATURN)]:
        result, _ = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
        transit_lon = result[0]

        diff = abs(transit_lon - bb.longitude)
        if diff > 180:
            diff = 360 - diff

        if diff <= orb:
            if planet_name == "Jupiter":
                effect = "positive"
                desc = "Bhrigu Bindu activated by Jupiter — significant positive event likely"
            else:
                effect = "karmic"
                desc = "Bhrigu Bindu activated by Saturn — karmic lessons and restructuring"

            activations.append({
                "planet": planet_name,
                "distance": round(diff, 2),
                "effect": effect,
                "description": desc,
            })

    return activations


# ===== Jupiter 12-House Cycle (Bhrigu Samhita) =====

JUPITER_HOUSE_RESULTS = {
    1: {
        "summary": "Jupiter in 1st — new beginnings, self-improvement, recognition",
        "career": "Natural authority and leadership emerge. Good for new roles.",
        "finance": "Moderate gains through personal effort.",
        "health": "Improved vitality and well-being. Recovery from past ailments.",
        "relationships": "Magnetic personality attracts beneficial connections.",
        "spiritual": "Self-awareness deepens. Guru's blessings flow.",
    },
    2: {
        "summary": "Jupiter in 2nd — wealth increase, family harmony",
        "career": "Income-related growth. Voice and speech become persuasive.",
        "finance": "Best period for wealth accumulation. Savings increase.",
        "health": "Watch dietary excess. Otherwise good.",
        "relationships": "Family bonds strengthen. Harmonious domestic life.",
        "spiritual": "Knowledge and wisdom in traditional learning.",
    },
    3: {
        "summary": "Jupiter in 3rd — courage, short travels, communications",
        "career": "Success through communication, writing, media. Short business trips.",
        "finance": "Moderate. Gains through effort and initiative.",
        "health": "Good energy for physical activities.",
        "relationships": "Improved sibling relations. New friendships.",
        "spiritual": "Pilgrimage to nearby sacred places.",
    },
    4: {
        "summary": "Jupiter in 4th — property gains, mother's blessings, vehicles",
        "career": "Success in real estate, agriculture, education sector.",
        "finance": "Property acquisition likely. Vehicle purchase favored.",
        "health": "Mental peace and emotional stability.",
        "relationships": "Domestic happiness. Mother's health improves.",
        "spiritual": "Inner peace. Interest in roots and traditions.",
    },
    5: {
        "summary": "Jupiter in 5th — children, creativity, romance, past merit fruits",
        "career": "Creative projects succeed. Recognition for intellect.",
        "finance": "Speculative gains possible. Investment returns.",
        "health": "Excellent vitality. Joy and enthusiasm.",
        "relationships": "Romance blossoms. Children bring happiness.",
        "spiritual": "Mantras become powerful. Past-life merit activates.",
    },
    6: {
        "summary": "Jupiter in 6th — enemy defeat, service, but health vigilance",
        "career": "Victory over competitors. Success in service and healing.",
        "finance": "Debts reduce. But avoid lending money.",
        "health": "Vulnerable period — get checkups. Digestive care needed.",
        "relationships": "Conflicts with enemies resolve. Some tension with colleagues.",
        "spiritual": "Service and karma yoga emphasized.",
    },
    7: {
        "summary": "Jupiter in 7th — partnerships, marriage, public dealings",
        "career": "Business partnerships succeed. Public recognition.",
        "finance": "Gains through partnerships and collaborations.",
        "health": "Partner's health may need attention.",
        "relationships": "Marriage prospects strong. Existing bonds deepen.",
        "spiritual": "Learning through relationships and partnerships.",
    },
    8: {
        "summary": "Jupiter in 8th — transformation, research, inheritance",
        "career": "Research and investigation succeed. Behind-the-scenes gains.",
        "finance": "Sudden financial changes. Inheritance or insurance possible.",
        "health": "Chronic issues may surface. Preventive care important.",
        "relationships": "Deep emotional transformations in relationships.",
        "spiritual": "Profound spiritual experiences. Occult knowledge attracts.",
    },
    9: {
        "summary": "Jupiter in 9th — highest fortune, dharma, guru blessings",
        "career": "Career reaches new heights. International opportunities.",
        "finance": "Excellent period for wealth. Fortune favors the bold.",
        "health": "Strong vitality. Blessed with good health.",
        "relationships": "Father's blessings. Beneficial mentors appear.",
        "spiritual": "Best period for spiritual growth. Pilgrimage. Guru darshan.",
    },
    10: {
        "summary": "Jupiter in 10th — career peak, authority, government favor",
        "career": "Promotion, new position, or career breakthrough. Government favors.",
        "finance": "Professional income increases significantly.",
        "health": "Good but watch stress from increased responsibilities.",
        "relationships": "Professional reputation enhances social standing.",
        "spiritual": "Karma yoga — spiritual progress through righteous work.",
    },
    11: {
        "summary": "Jupiter in 11th — maximum gains, wishes fulfilled, networking",
        "career": "All professional goals achievable. Network expansion.",
        "finance": "Highest earning potential. Multiple income sources.",
        "health": "Good vitality. Social activities bring joy.",
        "relationships": "Friendships bring opportunities. Elder siblings prosper.",
        "spiritual": "Wishes fulfilled. Collective spiritual activities.",
    },
    12: {
        "summary": "Jupiter in 12th — spiritual growth, foreign connections, expenses",
        "career": "Foreign opportunities. Career in spiritual or healing fields.",
        "finance": "Increased expenses but for good causes. Charitable tendencies.",
        "health": "Sleep and rest important. Hospital visits possible.",
        "relationships": "Some isolation needed. Long-distance connections.",
        "spiritual": "Best period for moksha, meditation, and retreat.",
    },
}


# ===== Saturn 30-Year Cycle =====

SATURN_HOUSE_RESULTS = {
    1: {
        "summary": "Saturn in 1st — self-discipline, health challenges, character building",
        "career": "Hard work required. Slow but steady progress through perseverance.",
        "health": "Physical endurance tested. Bone/joint care. Discipline in routine.",
        "relationships": "Self-reliance emphasized. Others may seem distant.",
    },
    2: {
        "summary": "Saturn in 2nd — financial restructuring, speech discipline",
        "career": "Income may feel restricted. Focus on savings.",
        "health": "Dental/throat issues possible. Diet discipline important.",
        "relationships": "Family responsibilities increase. Patience with elders.",
    },
    3: {
        "summary": "Saturn in 3rd — favorable, courage through hardship",
        "career": "Efforts bear fruit. Short travels for work succeed.",
        "health": "Good period. Physical strength increases.",
        "relationships": "Sibling relations tested then strengthen.",
    },
    4: {
        "summary": "Saturn in 4th — domestic challenges, property delays",
        "career": "Property matters face delays. Education requires extra effort.",
        "health": "Emotional heaviness. Mental peace disturbed.",
        "relationships": "Mother's health may need attention. Home renovations.",
    },
    5: {
        "summary": "Saturn in 5th — children matters, creative blocks then breakthroughs",
        "career": "Creative projects need more time. Intellectual discipline pays off.",
        "health": "Stomach issues possible. Moderate exercise helps.",
        "relationships": "Romance delayed or tested. Children need attention.",
    },
    6: {
        "summary": "Saturn in 6th — favorable, defeats enemies through persistence",
        "career": "Victory over competitors. Service-oriented work excels.",
        "health": "Chronic issues improve with discipline. Good for treatment.",
        "relationships": "Legal matters resolve. Employee relations improve.",
    },
    7: {
        "summary": "Saturn in 7th — partnership tests, marriage karmic lessons",
        "career": "Business partnerships need patience. Contracts face delays.",
        "health": "Partner's health may be affected.",
        "relationships": "Marriage tested but strengthened. Commitment solidifies.",
    },
    8: {
        "summary": "Saturn in 8th — transformation through difficulty",
        "career": "Sudden changes in career direction. Research deepens.",
        "health": "Most vulnerable period. Regular checkups essential.",
        "relationships": "Deep karmic lessons in relationships.",
    },
    9: {
        "summary": "Saturn in 9th — dharma tested, father's challenges",
        "career": "Long-distance work faces obstacles. Patience with superiors.",
        "health": "Hip/thigh issues possible. Travel fatigue.",
        "relationships": "Father's health may need attention. Guru relationship evolves.",
    },
    10: {
        "summary": "Saturn in 10th — career restructuring, authority through hard work",
        "career": "Career defining period. Recognition comes through sustained effort.",
        "health": "Knee/joint care. Work-related stress management needed.",
        "relationships": "Professional reputation built on integrity.",
    },
    11: {
        "summary": "Saturn in 11th — favorable, gains through discipline",
        "career": "Long-term goals materialize. Network of reliable contacts.",
        "health": "Good period. Steady health.",
        "relationships": "Loyal friendships. Elder siblings stable.",
    },
    12: {
        "summary": "Saturn in 12th — expenses, foreign settlement, spiritual discipline",
        "career": "Foreign opportunities through hard work. Behind-the-scenes roles.",
        "health": "Sleep disruptions. Hospital visits possible. Feet/ankle care.",
        "relationships": "Some isolation. Long-distance relationships.",
    },
}


# ===== Planet-House Classical Results (Bhrigu-style specifics) =====

PLANET_HOUSE_RESULTS = {
    "Sun": {
        1: "Strong personality, leadership quality, government connections. Father influential.",
        2: "Wealth through authority. Strong family values. Commanding speech.",
        3: "Courageous, good with siblings. Success in communication and media.",
        4: "Property through government. Strained relation with mother if afflicted.",
        5: "Intelligent children. Success in politics, speculation, creative arts.",
        6: "Defeats enemies. Good in service. Digestive care needed.",
        7: "Dominating in partnerships. Late marriage possible. Government spouse.",
        8: "Sudden events related to father. Interest in occult. Eye care needed.",
        9: "Fortunate, father is religious. Pilgrimage. Government favor for dharma.",
        10: "Best placement — authority, high position, fame. Government career.",
        11: "Income from government or authority. Fulfilled desires. Influential friends.",
        12: "Foreign government connections. Eye issues. Father may live abroad.",
    },
    "Moon": {
        1: "Attractive personality, popular, emotional nature. Strong intuition.",
        2: "Family-oriented wealth. Beautiful speech. Love for food and comfort.",
        3: "Imaginative mind. Frequent short travels. Close to siblings.",
        4: "Very favorable — domestic happiness, mother's love, property, vehicles.",
        5: "Emotional intelligence. Creative arts. Many children if well-aspected.",
        6: "Emotional health issues. Service-oriented. Stomach care needed.",
        7: "Beautiful spouse. Emotional partnerships. Early marriage possible.",
        8: "Emotional transformations. Inheritance from mother's side. Occult interest.",
        9: "Fortune through mother. Pilgrimage to water places. Spiritual inclination.",
        10: "Public popularity. Career in hospitality, nursing, or public service.",
        11: "Gains through women and public. Many friends. Wishes fulfilled.",
        12: "Foreign settlement. Spiritual nature. Sleep issues. Mother may live far.",
    },
    "Mars": {
        1: "Manglik. Brave, energetic, competitive nature. Scar on face/head possible.",
        2: "Manglik. Harsh speech. Wealth through land, property, engineering.",
        3: "Best placement — courageous, strong siblings, adventurous spirit.",
        4: "Manglik. Property disputes possible. Strong determination. Vehicle accidents caution.",
        5: "Technical education. Sons likely. Competitive in sports. Speculative risks.",
        6: "Excellent — defeats all enemies. Success in surgery, military, police.",
        7: "Manglik. Aggressive partner or partner in military/police. Early marriage issues.",
        8: "Manglik. Accidents possible. Surgery. Inheritance through conflict. Long life paradoxically.",
        9: "Dharma through action. Brother-like father. Property from father.",
        10: "Engineering, military, police career. Land dealings. Authoritative position.",
        11: "Gains through property, land, brothers. Fulfilled desires through courage.",
        12: "Manglik. Hospitalization possible. Foreign travels. Expenses on property.",
    },
    "Mercury": {
        1: "Intelligent, youthful appearance. Good communicator. Business acumen.",
        2: "Excellent speech. Wealth through trade and intellect. Family of scholars.",
        3: "Best placement — writing, media, communication success. Many travels.",
        4: "Education focus. Multiple properties. Mother is intelligent.",
        5: "Highly intelligent children. Success in exams, writing, advisory roles.",
        6: "Analytical mind defeats enemies. Good accountant. Skin care needed.",
        7: "Business partnerships. Intelligent spouse. Multiple business ventures.",
        8: "Research, astrology, occult mathematics. Nervous disorders possible.",
        9: "Higher education. Multiple degrees. Teaching. Publishing success.",
        10: "Career in business, communication, IT, finance. Versatile professional.",
        11: "Income through intelligence and contacts. Networking brings wealth.",
        12: "Foreign education. Writing in isolation. Nervous exhaustion possible.",
    },
    "Jupiter": {
        1: "Blessed personality. Wisdom, good health, optimism. Guru-like nature.",
        2: "Excellent for wealth. Large family. Sweet and truthful speech.",
        3: "Moderate — courage through wisdom. Religious siblings.",
        4: "Very favorable — property, vehicles, mother's blessings, higher education.",
        5: "Best placement — wise children, spiritual merit, advisory success.",
        6: "Mixed — defeats enemies but health expenditures. Legal victories.",
        7: "Wise and wealthy spouse. Successful partnerships. Late but good marriage.",
        8: "Longevity. Inheritance. Spiritual transformation. Some health setbacks.",
        9: "Excellent — highest dharma, foreign fortune, guru blessings, pilgrimage.",
        10: "High position through merit. Teacher, judge, advisor. Government respect.",
        11: "All desires fulfilled. Wealth, influential friends, elder siblings prosper.",
        12: "Spiritual liberation path. Foreign connections. Temple activities. Charitable.",
    },
    "Venus": {
        1: "Attractive, artistic, luxurious life. Charismatic personality.",
        2: "Wealth through arts, luxury, beauty industry. Beautiful family.",
        3: "Artistic communication. Sister-like relations. Short pleasure trips.",
        4: "Luxury vehicles, beautiful home, happy mother. Comfort-oriented life.",
        5: "Romantic nature. Artistic children. Success in entertainment.",
        6: "Challenges in love. Service in beauty/health industry. Reproductive care.",
        7: "Best for marriage — beautiful, devoted spouse. Successful partnerships.",
        8: "Inheritance from in-laws. Marital challenges. Tantric interests.",
        9: "Fortune through women. Foreign luxury. Artistic father.",
        10: "Career in arts, film, fashion, luxury goods. Diplomatic skills.",
        11: "Gains through women and arts. All comforts and desires fulfilled.",
        12: "Foreign luxury. Bedroom pleasures. Spiritual arts. Expenses on comfort.",
    },
    "Saturn": {
        1: "Disciplined, serious nature. Slow start in life but steady rise. Hard worker.",
        2: "Wealth through hard work and savings. Frugal speech. Traditional family.",
        3: "Very favorable — persistence, victory through patience. Younger siblings tested.",
        4: "Property delays then gains. Mother faces hardships. Home needs repairs.",
        5: "Delayed children. Disciplined intellect. Success in research and science.",
        6: "Excellent — defeats enemies through persistence. Long service career.",
        7: "Late marriage. Older or serious spouse. Partnerships need patience.",
        8: "Long life but chronic health issues. Inheritance delays. Transformation through suffering.",
        9: "Father faces challenges. Dharma through discipline. Late-life pilgrimage.",
        10: "Excellent for career — rise through hard work. Administration, law, construction.",
        11: "Steady income. Reliable friends. Long-term gains through perseverance.",
        12: "Foreign settlement through labor. Hospital work. Spiritual discipline.",
    },
    "Rahu": {
        1: "Unconventional personality. Foreign connections. Mysterious aura. Ambition.",
        2: "Wealth through unconventional means. Foreign food habits. Speech anomalies.",
        3: "Courageous in unconventional ways. Media, technology success.",
        4: "Foreign property. Unusual home environment. Adopted or foster connections.",
        5: "Unusual children or childbirth. Speculative mind. Research in occult.",
        6: "Excellent for defeating enemies. Success in foreign or unconventional medicine.",
        7: "Foreign or unconventional spouse. Inter-caste or inter-religion marriage.",
        8: "Occult mastery. Sudden events. Insurance gains. Research in hidden sciences.",
        9: "Unconventional beliefs. Foreign guru. Break from traditional dharma.",
        10: "Career in foreign companies, technology, politics. Sudden rise possible.",
        11: "Gains from foreign sources. Fulfilled desires through unconventional means.",
        12: "Foreign settlement. Spiritual confusion then clarity. Sleep disorders.",
    },
    "Ketu": {
        1: "Spiritual personality. Detached nature. Past-life karmic connections.",
        2: "Spiritual wealth. Detachment from family. Speech may be cryptic.",
        3: "Courage through spiritual strength. Communication in spiritual matters.",
        4: "Detachment from home. Spiritual education. Mother may be spiritual.",
        5: "Past-life merit. Spiritual children. Intuitive intelligence.",
        6: "Excellent for healing. Defeats enemies through spiritual power.",
        7: "Detachment in marriage. Spiritual partnership. Past-life spouse connection.",
        8: "Excellent for occult. Moksha yoga. Deep transformation. Psychic abilities.",
        9: "Deeply spiritual. Past-life dharma. Unconventional guru. Pilgrimage.",
        10: "Career through spiritual or healing work. Detachment from status.",
        11: "Gains through spiritual activities. Fulfilled desires through surrender.",
        12: "Best placement — moksha karaka. Spiritual liberation. Foreign ashram.",
    },
}


def get_planet_house_insight(planet_name: str, house: int) -> str:
    """Get classical Bhrigu-style result for planet in house."""
    planet_results = PLANET_HOUSE_RESULTS.get(planet_name, {})
    return planet_results.get(house, "")


def get_jupiter_cycle(house_from_lagna: int) -> dict:
    """Get Jupiter transit predictions for a specific house."""
    return JUPITER_HOUSE_RESULTS.get(house_from_lagna, {})


def get_saturn_cycle(house_from_lagna: int) -> dict:
    """Get Saturn transit predictions for a specific house."""
    return SATURN_HOUSE_RESULTS.get(house_from_lagna, {})
