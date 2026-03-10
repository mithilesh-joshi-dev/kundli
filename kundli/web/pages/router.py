"""HTML page routes — server-rendered with Jinja2 + HTMX partials."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ...calc.constants import RASHIS
from ...calc.engine import calculate_chart
from ...config import settings
from ..api.common import BirthInput, parse_birth
from ..firestore import store_request
from ..i18n import SUPPORTED_LANGUAGES, get_translator

logger = logging.getLogger("kundli.pages")

router = APIRouter()

# North Indian chart geometry (300x300 SVG)
# Houses are FIXED, rashis fill based on lagna. Counter-clockwise from top.
# Outer: TL(0,0) TR(300,0) BR(300,300) BL(0,300)
# Mid: T(150,0) R(300,150) B(150,300) L(0,150) C(150,150)
# Inner intersection: P1(75,75) P2(225,75) P3(225,225) P4(75,225)
_NORTH_INDIAN_HOUSES = {
    1:  {"points": "150,0 225,75 150,150 75,75",     "cx": 150, "cy": 68,   "num_x": 150, "num_y": 28},
    2:  {"points": "150,0 300,0 225,75",              "cx": 225, "cy": 22,   "num_x": 240, "num_y": 15},
    3:  {"points": "300,0 300,150 225,75",             "cx": 278, "cy": 68,   "num_x": 288, "num_y": 28},
    4:  {"points": "225,75 300,150 225,225 150,150",   "cx": 225, "cy": 150,  "num_x": 268, "num_y": 115},
    5:  {"points": "300,150 300,300 225,225",           "cx": 278, "cy": 228,  "num_x": 288, "num_y": 268},
    6:  {"points": "300,300 150,300 225,225",           "cx": 225, "cy": 278,  "num_x": 240, "num_y": 288},
    7:  {"points": "150,300 75,225 150,150 225,225",   "cx": 150, "cy": 232,  "num_x": 150, "num_y": 278},
    8:  {"points": "150,300 0,300 75,225",             "cx": 75,  "cy": 278,  "num_x": 60,  "num_y": 288},
    9:  {"points": "0,300 0,150 75,225",               "cx": 22,  "cy": 228,  "num_x": 12,  "num_y": 268},
    10: {"points": "75,75 150,150 75,225 0,150",       "cx": 75,  "cy": 150,  "num_x": 32,  "num_y": 115},
    11: {"points": "0,0 75,75 0,150",                  "cx": 22,  "cy": 68,   "num_x": 12,  "num_y": 28},
    12: {"points": "0,0 150,0 75,75",                  "cx": 75,  "cy": 22,   "num_x": 60,  "num_y": 15},
}


def _build_north_indian_chart(chart, lagna_rashi_idx: int, T) -> list[dict]:
    """Build house data for North Indian SVG chart."""
    house_planets = {i: [] for i in range(1, 13)}
    for p in chart.planets:
        house_planets[p.house].append({
            "name_local": T(f"planet.{p.name}"),
            "retro": p.is_retrograde,
        })

    houses_data = []
    for h in range(1, 13):
        rashi = RASHIS[(lagna_rashi_idx + h - 1) % 12]
        geo = _NORTH_INDIAN_HOUSES[h]
        houses_data.append({
            "number": h,
            "rashi": rashi,
            "rashi_local": T(f"rashi.{rashi}"),
            "planets": house_planets[h],
            **geo,
        })
    return houses_data


def _ctx(request: Request, page: str = "home", **kwargs):
    """Build template context with lang, T, and common vars."""
    lang = request.query_params.get("lang", settings.app.default_lang)
    T = get_translator(lang)
    return {
        "request": request,
        "lang": lang,
        "T": T,
        "page": page,
        "languages": SUPPORTED_LANGUAGES,
        "features": settings.features,
        **kwargs,
    }


# === Page Routes ===

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    ctx = _ctx(request, "home")
    return request.app.state.templates.TemplateResponse("pages/home.html", ctx)


@router.get("/chart", response_class=HTMLResponse)
async def chart_page(request: Request):
    ctx = _ctx(request, "chart")
    return request.app.state.templates.TemplateResponse("pages/chart.html", ctx)


@router.get("/predict", response_class=HTMLResponse)
async def predict_page(request: Request):
    ctx = _ctx(request, "predict")
    return request.app.state.templates.TemplateResponse("pages/predict.html", ctx)


@router.get("/transit", response_class=HTMLResponse)
async def transit_page(request: Request):
    ctx = _ctx(request, "transit")
    return request.app.state.templates.TemplateResponse("pages/transit.html", ctx)


@router.get("/match", response_class=HTMLResponse)
async def match_page(request: Request):
    ctx = _ctx(request, "match")
    return request.app.state.templates.TemplateResponse("pages/match.html", ctx)


# === HTMX Partial Routes (return rendered HTML fragments) ===

@router.post("/pages/chart/results", response_class=HTMLResponse)
async def chart_results(request: Request):
    form = await request.form()
    lang = form.get("lang", settings.app.default_lang)
    T = get_translator(lang)

    person_name = form.get("name", "").strip() or None
    body = BirthInput(
        name=person_name,
        date=form["date"], time=form["time"],
        place=form.get("place") or None,
        lat=float(form["lat"]) if form.get("lat") else None,
        lon=float(form["lon"]) if form.get("lon") else None,
        utc_offset=float(form.get("utc_offset", 5.5)),
        lang=lang,
    )
    birth = parse_birth(body)
    chart = calculate_chart(birth)

    # Build same data as API
    from ..api.chart import api_chart
    data = api_chart(body)

    # Build North Indian chart data
    lagna_rashi_idx = int(chart.lagna.longitude / 30) % 12
    houses_data = _build_north_indian_chart(chart, lagna_rashi_idx, T)

    store_request({
        "type": "chart", "name": person_name,
        "date": body.date, "time": body.time, "place": body.place,
        "lat": body.lat, "lon": body.lon, "utc_offset": body.utc_offset,
    })

    ctx = {
        "request": request,
        "T": T,
        "lang": lang,
        "data": data,
        "houses_data": houses_data,
        "person_name": person_name,
    }
    return request.app.state.templates.TemplateResponse("partials/chart_results.html", ctx)


@router.post("/pages/predict/results", response_class=HTMLResponse)
async def predict_results(request: Request):
    form = await request.form()
    lang = form.get("lang", settings.app.default_lang)
    T = get_translator(lang)

    from ..api.predict import PredictInput, api_predict
    person_name = form.get("name", "").strip() or None
    body = PredictInput(
        name=person_name,
        date=form["date"], time=form["time"],
        place=form.get("place") or None,
        lat=float(form["lat"]) if form.get("lat") else None,
        lon=float(form["lon"]) if form.get("lon") else None,
        utc_offset=float(form.get("utc_offset", 5.5)),
        start_year=int(form.get("start_year", 2026)),
        end_year=int(form.get("end_year", 2028)),
        lang=lang,
    )
    data = api_predict(body)

    store_request({
        "type": "predict", "name": person_name,
        "date": body.date, "time": body.time, "place": body.place,
        "lat": body.lat, "lon": body.lon, "utc_offset": body.utc_offset,
        "start_year": body.start_year, "end_year": body.end_year,
    })

    ctx = {"request": request, "T": T, "lang": lang, "data": data, "person_name": person_name}
    return request.app.state.templates.TemplateResponse("partials/predict_results.html", ctx)


@router.post("/pages/transit/results", response_class=HTMLResponse)
async def transit_results(request: Request):
    form = await request.form()
    lang = form.get("lang", settings.app.default_lang)
    T = get_translator(lang)

    from ..api.transit import TransitInput, api_transit
    person_name = form.get("name", "").strip() or None
    body = TransitInput(
        name=person_name,
        date=form["date"], time=form["time"],
        place=form.get("place") or None,
        lat=float(form["lat"]) if form.get("lat") else None,
        lon=float(form["lon"]) if form.get("lon") else None,
        utc_offset=float(form.get("utc_offset", 5.5)),
        start_year=int(form.get("start_year", 2026)),
        end_year=int(form.get("end_year", 2028)),
        lang=lang,
    )
    data = api_transit(body)

    store_request({
        "type": "transit", "name": person_name,
        "date": body.date, "time": body.time, "place": body.place,
        "lat": body.lat, "lon": body.lon, "utc_offset": body.utc_offset,
        "start_year": body.start_year, "end_year": body.end_year,
    })

    ctx = {"request": request, "T": T, "lang": lang, "data": data, "person_name": person_name}
    return request.app.state.templates.TemplateResponse("partials/transit_results.html", ctx)


@router.post("/pages/match/results", response_class=HTMLResponse)
async def match_results(request: Request):
    form = await request.form()
    lang = form.get("lang", settings.app.default_lang)
    T = get_translator(lang)

    from ..api.matching import MatchInput, api_matching
    bride_name = form.get("bride_name", "").strip() or None
    groom_name = form.get("groom_name", "").strip() or None
    bride = BirthInput(
        name=bride_name,
        date=form["bride_date"], time=form["bride_time"],
        place=form.get("bride_place") or None,
        lat=float(form["bride_lat"]) if form.get("bride_lat") else None,
        lon=float(form["bride_lon"]) if form.get("bride_lon") else None,
        utc_offset=float(form.get("bride_utc_offset", 5.5)),
        lang=lang,
    )
    groom = BirthInput(
        name=groom_name,
        date=form["groom_date"], time=form["groom_time"],
        place=form.get("groom_place") or None,
        lat=float(form["groom_lat"]) if form.get("groom_lat") else None,
        lon=float(form["groom_lon"]) if form.get("groom_lon") else None,
        utc_offset=float(form.get("groom_utc_offset", 5.5)),
        lang=lang,
    )
    body = MatchInput(bride=bride, groom=groom, lang=lang)
    data = api_matching(body)

    store_request({
        "type": "match",
        "bride": {
            "name": bride_name, "date": bride.date, "time": bride.time,
            "place": bride.place, "lat": bride.lat, "lon": bride.lon,
            "utc_offset": bride.utc_offset,
        },
        "groom": {
            "name": groom_name, "date": groom.date, "time": groom.time,
            "place": groom.place, "lat": groom.lat, "lon": groom.lon,
            "utc_offset": groom.utc_offset,
        },
    })

    ctx = {"request": request, "T": T, "lang": lang, "data": data, "bride_name": bride_name, "groom_name": groom_name}
    return request.app.state.templates.TemplateResponse("partials/match_results.html", ctx)
