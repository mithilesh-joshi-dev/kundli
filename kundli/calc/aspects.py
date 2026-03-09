"""Vedic (Graha Drishti) planetary aspects."""

from ..models import Chart, PlanetPosition

# Standard Vedic aspects: all planets aspect 7th house from themselves.
# Special aspects:
#   Mars: 4th and 8th
#   Jupiter: 5th and 9th
#   Saturn: 3rd and 10th
#   Rahu/Ketu: 5th, 7th, 9th (some traditions)

SPECIAL_ASPECTS = {
    "Mars": [4, 8],
    "Jupiter": [5, 9],
    "Saturn": [3, 10],
    "Rahu": [5, 9],
    "Ketu": [5, 9],
}


def get_aspects(chart: Chart) -> list[tuple[str, str, int]]:
    """Return list of (aspecting_planet, aspected_planet, aspect_house_distance)."""
    all_bodies = chart.planets
    aspects = []

    for planet in all_bodies:
        # Houses this planet aspects
        aspect_distances = [7]  # All planets aspect 7th
        if planet.name in SPECIAL_ASPECTS:
            aspect_distances.extend(SPECIAL_ASPECTS[planet.name])

        for dist in aspect_distances:
            target_house = ((planet.house - 1 + dist) % 12) + 1
            # Find planets in that house
            for other in all_bodies:
                if other.name != planet.name and other.house == target_house:
                    aspects.append((planet.name, other.name, dist))

    return aspects


def get_house_aspects(chart: Chart) -> dict[int, list[str]]:
    """Return dict of house -> list of planets aspecting that house."""
    house_aspects: dict[int, list[str]] = {i: [] for i in range(1, 13)}

    for planet in chart.planets:
        aspect_distances = [7]
        if planet.name in SPECIAL_ASPECTS:
            aspect_distances.extend(SPECIAL_ASPECTS[planet.name])

        for dist in aspect_distances:
            target_house = ((planet.house - 1 + dist) % 12) + 1
            house_aspects[target_house].append(planet.name)

    return house_aspects
