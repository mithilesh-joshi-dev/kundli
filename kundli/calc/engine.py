import swisseph as swe

from ..models import BirthData, Chart, PlanetPosition
from .constants import AYANAMSHA, PLANETS
from .utils import dms_str, longitude_to_nakshatra, longitude_to_rashi, to_julian_day


def _make_position(name: str, lon: float, lagna_rashi_idx: int,
                   is_retrograde: bool = False) -> PlanetPosition:
    rashi_idx, rashi, rashi_deg = longitude_to_rashi(lon)
    _, nakshatra, pada = longitude_to_nakshatra(lon)
    # Whole Sign house: house 1 = lagna's rashi
    house = ((rashi_idx - lagna_rashi_idx) % 12) + 1
    return PlanetPosition(
        name=name,
        longitude=lon,
        rashi=rashi,
        rashi_degree=rashi_deg,
        nakshatra=nakshatra,
        nakshatra_pada=pada,
        house=house,
        is_retrograde=is_retrograde,
    )


def calculate_chart(birth: BirthData) -> Chart:
    """Calculate a Vedic birth chart from birth data."""
    swe.set_ephe_path(None)  # Use built-in Moshier ephemeris
    swe.set_sid_mode(AYANAMSHA)

    jd = to_julian_day(
        birth.year, birth.month, birth.day,
        birth.hour, birth.minute, birth.second,
        birth.utc_offset,
    )

    ayanamsha_value = swe.get_ayanamsa_ut(jd)

    # House cusps and ascendant (Whole Sign)
    cusps, ascmc = swe.houses_ex(
        jd, birth.latitude, birth.longitude,
        b"W", swe.FLG_SIDEREAL,
    )
    asc_lon = ascmc[0]

    # Lagna
    lagna_rashi_idx = int(asc_lon / 30) % 12
    lagna = _make_position("Lagna", asc_lon, lagna_rashi_idx)

    # Planets
    planets = []
    rahu_lon = None
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

    for name, planet_id in PLANETS.items():
        if name == "Ketu":
            continue  # Handle after Rahu
        result, _ = swe.calc_ut(jd, planet_id, flags)
        lon = result[0]
        speed = result[3]
        is_retro = speed < 0

        if name == "Rahu":
            rahu_lon = lon
            # Rahu is always retrograde in mean node
            is_retro = True

        planets.append(_make_position(name, lon, lagna_rashi_idx, is_retro))

    # Ketu = Rahu + 180
    ketu_lon = (rahu_lon + 180) % 360
    planets.append(_make_position("Ketu", ketu_lon, lagna_rashi_idx, True))

    swe.close()

    return Chart(
        birth_data=birth,
        ayanamsha_value=ayanamsha_value,
        lagna=lagna,
        planets=planets,
    )
