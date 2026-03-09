"""Detection of common Vedic astrology yogas."""

from ..models import Chart

KENDRA_HOUSES = {1, 4, 7, 10}
TRIKONA_HOUSES = {1, 5, 9}
TRIK_HOUSES = {6, 8, 12}
UPACHAYA_HOUSES = {3, 6, 10, 11}


def _planet_map(chart: Chart) -> dict[str, int]:
    """Map planet name -> house number."""
    return {p.name: p.house for p in chart.planets}


def _planets_in_house(chart: Chart, house: int) -> list[str]:
    return [p.name for p in chart.planets if p.house == house]


def _planet_rashi(chart: Chart, name: str) -> str:
    for p in chart.planets:
        if p.name == name:
            return p.rashi
    return ""


def detect_yogas(chart: Chart) -> list[tuple[str, str]]:
    """Return list of (yoga_name, description)."""
    yogas = []
    pm = _planet_map(chart)

    # 1. Gajakesari Yoga: Jupiter in kendra from Moon
    if "Jupiter" in pm and "Moon" in pm:
        diff = ((pm["Jupiter"] - pm["Moon"]) % 12)
        if diff in {0, 3, 6, 9}:
            yogas.append(("Gajakesari Yoga",
                          "Jupiter in kendra from Moon — wisdom, wealth, and reputation"))

    # 2. Budhaditya Yoga: Sun and Mercury in same house
    if "Sun" in pm and "Mercury" in pm and pm["Sun"] == pm["Mercury"]:
        yogas.append(("Budhaditya Yoga",
                      "Sun-Mercury conjunction — intelligence and communication skills"))

    # 3. Chandra-Mangal Yoga: Moon and Mars in same house
    if "Moon" in pm and "Mars" in pm and pm["Moon"] == pm["Mars"]:
        yogas.append(("Chandra-Mangal Yoga",
                      "Moon-Mars conjunction — wealth through bold actions"))

    # 4. Guru-Mangal Yoga: Jupiter and Mars in same house
    if "Jupiter" in pm and "Mars" in pm and pm["Jupiter"] == pm["Mars"]:
        yogas.append(("Guru-Mangal Yoga",
                      "Jupiter-Mars conjunction — courage with wisdom"))

    # 5. Pancha Mahapurusha Yogas (Mars/Mercury/Jupiter/Venus/Saturn in own/exalted sign in kendra)
    mahapurusha = {
        "Mars": ("Ruchaka Yoga", "Mars in own/exalted sign in kendra — valor and leadership"),
        "Mercury": ("Bhadra Yoga", "Mercury in own/exalted sign in kendra — intellect and eloquence"),
        "Jupiter": ("Hamsa Yoga", "Jupiter in own/exalted sign in kendra — righteousness and fortune"),
        "Venus": ("Malavya Yoga", "Venus in own/exalted sign in kendra — luxury and charm"),
        "Saturn": ("Shasha Yoga", "Saturn in own/exalted sign in kendra — authority and discipline"),
    }
    from .strength import OWN_SIGNS, EXALTATION
    for planet_name, (yoga_name, desc) in mahapurusha.items():
        if planet_name in pm and pm[planet_name] in KENDRA_HOUSES:
            rashi = _planet_rashi(chart, planet_name)
            is_own = rashi in OWN_SIGNS.get(planet_name, [])
            is_exalted = EXALTATION.get(planet_name, (None,))[0] == rashi
            if is_own or is_exalted:
                yogas.append((yoga_name, desc))

    # 6. Viparita Raja Yoga: Lords of 6/8/12 in 6/8/12
    # (Simplified: check if planets in trik houses are lords of other trik houses)
    from .strength import RASHI_LORDS
    from .constants import RASHIS
    lagna_rashi_idx = int(chart.lagna.longitude / 30) % 12
    house_rashis = {h: RASHIS[(lagna_rashi_idx + h - 1) % 12] for h in range(1, 13)}
    house_lords = {h: RASHI_LORDS[house_rashis[h]] for h in range(1, 13)}

    trik_lords = {house_lords[h] for h in TRIK_HOUSES}
    for planet in chart.planets:
        if planet.name in trik_lords and planet.house in TRIK_HOUSES:
            # Check it's lord of a trik house
            for h in TRIK_HOUSES:
                if house_lords[h] == planet.name and planet.house in TRIK_HOUSES and planet.house != h:
                    yogas.append(("Viparita Raja Yoga",
                                  f"{planet.name} (lord of house {h}) in house {planet.house} — "
                                  f"success through adversity"))
                    break

    # 7. Kemadruma Yoga: No planet in 2nd or 12th from Moon (except Sun, Rahu, Ketu)
    if "Moon" in pm:
        moon_house = pm["Moon"]
        h2 = (moon_house % 12) + 1
        h12 = ((moon_house - 2) % 12) + 1
        flanking = [p.name for p in chart.planets
                    if p.house in (h2, h12) and p.name not in ("Sun", "Rahu", "Ketu", "Moon")]
        if not flanking:
            yogas.append(("Kemadruma Yoga",
                          "No planets flanking Moon — indicates struggles, but cancellation possible"))

    # 8. Dhana Yoga: Lords of 2nd and 11th in kendra or trikona
    lord_2 = house_lords[2]
    lord_11 = house_lords[11]
    if lord_2 in pm and lord_11 in pm:
        if (pm[lord_2] in KENDRA_HOUSES | TRIKONA_HOUSES and
                pm[lord_11] in KENDRA_HOUSES | TRIKONA_HOUSES):
            yogas.append(("Dhana Yoga",
                          f"Lords of 2nd ({lord_2}) and 11th ({lord_11}) well placed — wealth"))

    # 9. Raja Yoga: Lord of trikona + lord of kendra conjunct or in mutual kendra
    trikona_lords = {house_lords[h] for h in TRIKONA_HOUSES if h != 1}
    kendra_lords = {house_lords[h] for h in KENDRA_HOUSES if h != 1}
    for tl in trikona_lords:
        for kl in kendra_lords:
            if tl != kl and tl in pm and kl in pm:
                if pm[tl] == pm[kl]:
                    yogas.append(("Raja Yoga",
                                  f"{tl} (trikona lord) conjunct {kl} (kendra lord) — "
                                  f"power and success"))

    # 10. Manglik check (Mars in 1, 2, 4, 7, 8, 12)
    if "Mars" in pm and pm["Mars"] in {1, 2, 4, 7, 8, 12}:
        yogas.append(("Manglik Dosha",
                      f"Mars in house {pm['Mars']} — Mangal Dosha present (important for marriage compatibility)"))

    return yogas
