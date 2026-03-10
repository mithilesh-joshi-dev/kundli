"""Chart API endpoint."""

from fastapi import APIRouter

from ...calc.aspects import get_aspects, get_house_aspects
from ...calc.constants import NAKSHATRA_LORDS, NAKSHATRAS, RASHIS
from ...calc.dasha import calculate_dasha
from ...calc.engine import calculate_chart
from ...calc.navamsa import calculate_navamsa
from ...calc.panchang import calculate_panchang
from ...calc.strength import RASHI_LORDS, get_dignity
from ...calc.utils import dms_str
from ...calc.yogas import detect_yogas
from ..i18n import get_translator
from .common import BirthInput, parse_birth, serialize_planet

router = APIRouter()


@router.post("/chart")
def api_chart(body: BirthInput):
    T = get_translator(body.lang)
    birth = parse_birth(body)
    chart = calculate_chart(birth)

    b = chart.birth_data
    lagna_rashi_idx = int(chart.lagna.longitude / 30) % 12

    # Panchang
    panchang = calculate_panchang(
        b.year, b.month, b.day, b.hour, b.minute, b.second, b.utc_offset)

    # Planets
    planets = [serialize_planet(p, T) for p in chart.planets]

    # Houses
    houses = []
    house_occupants = {i: [] for i in range(1, 13)}
    for p in chart.planets:
        house_occupants[p.house].append(p.name)
    house_asp = get_house_aspects(chart)

    for h in range(1, 13):
        rashi = RASHIS[(lagna_rashi_idx + h - 1) % 12]
        lord = RASHI_LORDS[rashi]
        houses.append({
            "number": h,
            "rashi": rashi,
            "rashi_local": T(f"rashi.{rashi}"),
            "lord": lord,
            "lord_local": T(f"planet.{lord}"),
            "planets": [{"name": n, "name_local": T(f"planet.{n}")} for n in house_occupants[h]],
            "aspects": [{"name": n, "name_local": T(f"planet.{n}")} for n in house_asp[h]],
        })

    # Navamsa
    navamsa = []
    for name, rashi, house in calculate_navamsa(chart):
        navamsa.append({
            "name": name,
            "name_local": T(f"planet.{name}"),
            "rashi": rashi,
            "rashi_local": T(f"rashi.{rashi}"),
            "house": house,
        })

    # Yogas
    yogas = [{"name": n, "description": d} for n, d in detect_yogas(chart)]

    # Aspects
    aspects = []
    for src, tgt, dist in get_aspects(chart):
        aspects.append({
            "source": src, "source_local": T(f"planet.{src}"),
            "target": tgt, "target_local": T(f"planet.{tgt}"),
            "distance": dist,
        })

    # Dasha
    from datetime import datetime
    now = datetime.now()
    dashas = []
    for lord, start, end, antardashas in calculate_dasha(chart):
        is_active = start <= now < end
        ads = []
        for al, a_start, a_end in antardashas:
            ads.append({
                "lord": al, "lord_local": T(f"planet.{al}"),
                "start": a_start.strftime("%Y-%m-%d"),
                "end": a_end.strftime("%Y-%m-%d"),
                "is_active": a_start <= now < a_end,
            })
        dashas.append({
            "lord": lord, "lord_local": T(f"planet.{lord}"),
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "is_active": is_active,
            "antardashas": ads,
        })

    # Moon info for panchang
    moon = next((p for p in chart.planets if p.name == "Moon"), chart.planets[0])
    nak_idx = NAKSHATRAS.index(moon.nakshatra)

    return {
        "lang": body.lang,
        "birth": {
            "date": f"{b.year}-{b.month:02d}-{b.day:02d}",
            "time": f"{b.hour:02d}:{b.minute:02d}:{b.second:02d}",
            "lat": b.latitude,
            "lon": b.longitude,
            "utc_offset": b.utc_offset,
        },
        "ayanamsha": round(chart.ayanamsha_value, 4),
        "lagna": serialize_planet(chart.lagna, T),
        "planets": planets,
        "houses": houses,
        "panchang": {
            "vara": panchang["vara"],
            "vara_local": T(f"vara.{panchang['vara']}"),
            "tithi": panchang["tithi"],
            "yoga": panchang["yoga"],
            "karana": panchang["karana"],
            "birth_star": moon.nakshatra,
            "birth_star_local": T(f"nakshatra.{moon.nakshatra}"),
            "birth_star_pada": moon.nakshatra_pada,
            "nakshatra_lord": NAKSHATRA_LORDS[nak_idx],
        },
        "navamsa": navamsa,
        "yogas": yogas,
        "aspects": aspects,
        "dashas": dashas,
    }
