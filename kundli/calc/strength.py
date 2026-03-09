"""Planetary dignity — own sign, exaltation, debilitation, mooltrikona, friends/enemies."""

from ..models import PlanetPosition

# Rashi lords (0-indexed rashi -> planet name)
RASHI_LORDS = {
    "Mesha": "Mars", "Vrishabha": "Venus", "Mithuna": "Mercury",
    "Karka": "Moon", "Simha": "Sun", "Kanya": "Mercury",
    "Tula": "Venus", "Vrischika": "Mars", "Dhanu": "Jupiter",
    "Makara": "Saturn", "Kumbha": "Saturn", "Meena": "Jupiter",
}

# Exaltation sign and exact degree
EXALTATION = {
    "Sun": ("Mesha", 10), "Moon": ("Vrishabha", 3), "Mars": ("Makara", 28),
    "Mercury": ("Kanya", 15), "Jupiter": ("Karka", 5), "Venus": ("Meena", 27),
    "Saturn": ("Tula", 20), "Rahu": ("Vrishabha", 20), "Ketu": ("Vrischika", 20),
}

# Debilitation sign and exact degree
DEBILITATION = {
    "Sun": ("Tula", 10), "Moon": ("Vrischika", 3), "Mars": ("Karka", 28),
    "Mercury": ("Meena", 15), "Jupiter": ("Makara", 5), "Venus": ("Kanya", 27),
    "Saturn": ("Mesha", 20), "Rahu": ("Vrischika", 20), "Ketu": ("Vrishabha", 20),
}

# Mooltrikona sign and degree range (start, end)
MOOLTRIKONA = {
    "Sun": ("Simha", 0, 20), "Moon": ("Vrishabha", 3, 30),
    "Mars": ("Mesha", 0, 12), "Mercury": ("Kanya", 15, 20),
    "Jupiter": ("Dhanu", 0, 10), "Venus": ("Tula", 0, 15),
    "Saturn": ("Kumbha", 0, 20),
}

# Own signs
OWN_SIGNS = {
    "Sun": ["Simha"], "Moon": ["Karka"],
    "Mars": ["Mesha", "Vrischika"], "Mercury": ["Mithuna", "Kanya"],
    "Jupiter": ["Dhanu", "Meena"], "Venus": ["Vrishabha", "Tula"],
    "Saturn": ["Makara", "Kumbha"],
}

# Natural friendships
FRIENDS = {
    "Sun": ["Moon", "Mars", "Jupiter"],
    "Moon": ["Sun", "Mercury"],
    "Mars": ["Sun", "Moon", "Jupiter"],
    "Mercury": ["Sun", "Venus"],
    "Jupiter": ["Sun", "Moon", "Mars"],
    "Venus": ["Mercury", "Saturn"],
    "Saturn": ["Mercury", "Venus"],
}

ENEMIES = {
    "Sun": ["Venus", "Saturn"],
    "Moon": [],
    "Mars": ["Mercury"],
    "Mercury": ["Moon"],
    "Jupiter": ["Mercury", "Venus"],
    "Venus": ["Sun", "Moon"],
    "Saturn": ["Sun", "Moon", "Mars"],
}

NEUTRALS = {
    "Sun": ["Mercury"],
    "Moon": ["Mars", "Jupiter", "Venus", "Saturn"],
    "Mars": ["Venus", "Saturn"],
    "Mercury": ["Mars", "Jupiter", "Saturn"],
    "Jupiter": ["Saturn"],
    "Venus": ["Mars", "Jupiter"],
    "Saturn": ["Jupiter"],
}


def get_dignity(planet: PlanetPosition) -> str:
    """Return the dignity status of a planet."""
    name = planet.name
    rashi = planet.rashi
    deg = planet.rashi_degree

    if name in ("Rahu", "Ketu", "Lagna"):
        if name in EXALTATION and EXALTATION[name][0] == rashi:
            return "Exalted"
        if name in DEBILITATION and DEBILITATION[name][0] == rashi:
            return "Debilitated"
        return ""

    # Check Mooltrikona first (subset of own sign)
    if name in MOOLTRIKONA:
        mt_rashi, mt_start, mt_end = MOOLTRIKONA[name]
        if rashi == mt_rashi and mt_start <= deg < mt_end:
            return "Mooltrikona"

    # Exaltation
    if name in EXALTATION and EXALTATION[name][0] == rashi:
        return "Exalted"

    # Debilitation
    if name in DEBILITATION and DEBILITATION[name][0] == rashi:
        return "Debilitated"

    # Own sign
    if name in OWN_SIGNS and rashi in OWN_SIGNS[name]:
        return "Own Sign"

    # Friend/Enemy/Neutral
    rashi_lord = RASHI_LORDS.get(rashi, "")
    if rashi_lord == name:
        return "Own Sign"
    if name in FRIENDS and rashi_lord in FRIENDS[name]:
        return "Friendly"
    if name in ENEMIES and rashi_lord in ENEMIES[name]:
        return "Enemy"
    if name in NEUTRALS and rashi_lord in NEUTRALS[name]:
        return "Neutral"

    return ""
