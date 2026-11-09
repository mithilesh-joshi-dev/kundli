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
    2:  {"points": "0,0 150,0 75,75",                 "cx": 75,  "cy": 22,   "num_x": 60,  "num_y": 15},
    3:  {"points": "0,0 75,75 0,150",                 "cx": 22,  "cy": 68,   "num_x": 12,  "num_y": 28},
    4:  {"points": "75,75 150,150 75,225 0,150",      "cx": 75,  "cy": 150,  "num_x": 32,  "num_y": 115},
    5:  {"points": "0,300 0,150 75,225",              "cx": 22,  "cy": 228,  "num_x": 12,  "num_y": 268},
    6:  {"points": "150,300 0,300 75,225",            "cx": 75,  "cy": 278,  "num_x": 60,  "num_y": 288},
    7:  {"points": "150,300 75,225 150,150 225,225",  "cx": 150, "cy": 232,  "num_x": 150, "num_y": 278},
    8:  {"points": "300,300 150,300 225,225",          "cx": 225, "cy": 278,  "num_x": 240, "num_y": 288},
    9:  {"points": "300,150 300,300 225,225",          "cx": 278, "cy": 228,  "num_x": 288, "num_y": 268},
    10: {"points": "225,75 300,150 225,225 150,150",  "cx": 225, "cy": 150,  "num_x": 268, "num_y": 115},
    11: {"points": "300,0 300,150 225,75",            "cx": 278, "cy": 68,   "num_x": 288, "num_y": 28},
    12: {"points": "150,0 300,0 225,75",              "cx": 225, "cy": 22,   "num_x": 240, "num_y": 15},
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
    from ..auth import ALL_FEATURES
    lang = request.query_params.get("lang", settings.app.default_lang)
    T = get_translator(lang)
    user = getattr(request.state, "user", None)
    profile = getattr(request.state, "profile", None)
    user_features = getattr(request.state, "user_features", None) or set(ALL_FEATURES)
    return {
        "request": request,
        "lang": lang,
        "T": T,
        "page": page,
        "languages": SUPPORTED_LANGUAGES,
        "features": settings.features,
        "user_features": user_features,
        "current_user": user,
        "user_profile": profile,
        **kwargs,
    }


def _require_feature(request: Request, feature: str):
    """Raise 403 if the signed-in user does not have access to this feature."""
    from fastapi import HTTPException
    from ..auth import ALL_FEATURES
    user_features = getattr(request.state, "user_features", None) or set(ALL_FEATURES)
    if feature not in user_features:
        raise HTTPException(403, "या वैशिष्ट्यासाठी परवानगी नाही. कृपया प्रशासकाशी संपर्क साधा.")


# === Page Routes ===

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    from ...config import settings as cfg
    ctx = {
        "request": request,
        "firebase": cfg.firebase,
    }
    return request.app.state.templates.TemplateResponse(request, name="pages/login.html", context=ctx)


@router.get("/pending", response_class=HTMLResponse)
async def pending_page(request: Request):
    ctx = {
        "request": request,
        "current_user": getattr(request.state, "user", None),
    }
    return request.app.state.templates.TemplateResponse(request, name="pages/pending.html", context=ctx)


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    ctx = _ctx(request, "profile")
    return request.app.state.templates.TemplateResponse(request, name="pages/profile.html", context=ctx)


@router.post("/profile", response_class=HTMLResponse)
async def profile_save(request: Request):
    from ..auth import update_profile
    form = await request.form()
    display_name = form.get("display_name", "").strip()
    credentials  = form.get("credentials", "").strip()

    user = getattr(request.state, "user", None)
    if user and display_name:
        await update_profile(user["uid"], display_name, credentials)
        # Refresh cached profile on request.state so nav updates immediately
        request.state.profile = {
            **(request.state.profile or {}),
            "display_name": display_name,
            "credentials": credentials,
        }

    ctx = _ctx(request, "profile", saved=True)
    return request.app.state.templates.TemplateResponse(request, name="pages/profile.html", context=ctx)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    ctx = _ctx(request, "home")
    return request.app.state.templates.TemplateResponse(request, name="pages/home.html", context=ctx)


@router.get("/chart", response_class=HTMLResponse)
async def chart_page(request: Request):
    _require_feature(request, "chart")
    ctx = _ctx(request, "chart")
    return request.app.state.templates.TemplateResponse(request, name="pages/chart.html", context=ctx)


@router.get("/predict", response_class=HTMLResponse)
async def predict_page(request: Request):
    _require_feature(request, "predict")
    ctx = _ctx(request, "predict")
    return request.app.state.templates.TemplateResponse(request, name="pages/predict.html", context=ctx)


@router.get("/transit", response_class=HTMLResponse)
async def transit_page(request: Request):
    _require_feature(request, "transit")
    ctx = _ctx(request, "transit")
    return request.app.state.templates.TemplateResponse(request, name="pages/transit.html", context=ctx)


@router.get("/match", response_class=HTMLResponse)
async def match_page(request: Request):
    _require_feature(request, "match")
    ctx = _ctx(request, "match")
    return request.app.state.templates.TemplateResponse(request, name="pages/match.html", context=ctx)


@router.get("/questions", response_class=HTMLResponse)
async def questions_page(request: Request):
    _require_feature(request, "questions")
    from ...calc.events2 import EVENTS
    ctx = _ctx(request, "questions", events=EVENTS)
    return request.app.state.templates.TemplateResponse(request, name="pages/questions.html", context=ctx)


# ── Admin routes ──────────────────────────────────────────────────────────────

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    profile = getattr(request.state, "profile", None)
    if not profile or not profile.get("is_admin"):
        from fastapi import HTTPException
        raise HTTPException(403, "Admin access required")
    from ..auth import get_all_users, ALL_FEATURES, FEATURE_LABELS
    users = await get_all_users()
    ctx = _ctx(request, "admin",
               users=users,
               all_features=ALL_FEATURES,
               feature_labels=FEATURE_LABELS)
    return request.app.state.templates.TemplateResponse(request, name="pages/admin.html", context=ctx)


@router.post("/admin/users/{uid}/approve", response_class=HTMLResponse)
async def admin_approve_user(uid: str, request: Request):
    profile = getattr(request.state, "profile", None)
    if not profile or not profile.get("is_admin"):
        from fastapi import HTTPException
        raise HTTPException(403, "Admin access required")
    from ..auth import update_user_approval
    form = await request.form()
    approved = form.get("approved") == "1"
    await update_user_approval(uid, approved)
    if approved:
        return HTMLResponse(
            f'<button hx-post="/admin/users/{uid}/approve" hx-vals=\'{{"approved":"0"}}\' '
            f'hx-target="#approval-{uid}" hx-swap="outerHTML" '
            f'class="text-[10px] font-medium bg-green-50 text-green-700 border border-green-200 '
            f'rounded-full px-2 py-0.5 hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition cursor-pointer" '
            f'id="approval-{uid}">✓ Approved</button>'
        )
    else:
        return HTMLResponse(
            f'<button hx-post="/admin/users/{uid}/approve" hx-vals=\'{{"approved":"1"}}\' '
            f'hx-target="#approval-{uid}" hx-swap="outerHTML" '
            f'class="text-[10px] font-medium bg-orange-50 text-orange-600 border border-orange-100 '
            f'rounded-full px-2 py-0.5 hover:bg-green-50 hover:text-green-700 hover:border-green-200 transition cursor-pointer" '
            f'id="approval-{uid}">⏳ Pending</button>'
        )


@router.post("/admin/users/{uid}/features", response_class=HTMLResponse)
async def admin_update_user_features(uid: str, request: Request):
    profile = getattr(request.state, "profile", None)
    if not profile or not profile.get("is_admin"):
        from fastapi import HTTPException
        raise HTTPException(403, "Admin access required")
    from ..auth import update_user_features, ALL_FEATURES
    form = await request.form()
    features = [f for f in ALL_FEATURES if form.get(f)]
    await update_user_features(uid, features)
    return HTMLResponse('<span class="text-xs font-semibold text-green-600">✓ सेव झाले</span>')


# === HTMX Partial Routes (return rendered HTML fragments) ===

@router.post("/pages/chart/results", response_class=HTMLResponse)
async def chart_results(request: Request):
    form = await request.form()
    lang = form.get("lang", settings.app.default_lang)
    T = get_translator(lang)

    person_name = form.get("name", "").strip() or None
    gender  = form.get("gender", "").strip() or None
    gotra   = form.get("gotra", "").strip() or None
    parents = form.get("parents", "").strip() or None
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

    from ..auth import ALL_FEATURES
    user_features = getattr(request.state, "user_features", None) or set(ALL_FEATURES)
    ctx = {
        "request": request,
        "T": T,
        "lang": lang,
        "data": data,
        "houses_data": houses_data,
        "person_name": person_name,
        "place_name": body.place or "",
        "gender": gender or "",
        "gotra": gotra or "",
        "parents": parents or "",
        "user_features": user_features,
    }
    return request.app.state.templates.TemplateResponse(request, name="partials/chart_results.html", context=ctx)


@router.post("/pages/predict/results", response_class=HTMLResponse)
async def predict_results(request: Request):
    form = await request.form()
    lang = form.get("lang", settings.app.default_lang)
    T = get_translator(lang)

    from ..api.predict import PredictInput, api_predict  # uses predict2 via api
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
    return request.app.state.templates.TemplateResponse(request, name="partials/predict_results.html", context=ctx)


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
    return request.app.state.templates.TemplateResponse(request, name="partials/transit_results.html", context=ctx)


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
    return request.app.state.templates.TemplateResponse(request, name="partials/match_results.html", context=ctx)


@router.post("/pages/questions/results", response_class=HTMLResponse)
async def questions_results(request: Request):
    form = await request.form()
    lang = form.get("lang", settings.app.default_lang)
    T = get_translator(lang)

    from ...calc.analysis import build_analysis
    from ...calc.engine import calculate_chart
    from ...calc.events2 import predict_event

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
    ana = build_analysis(chart)

    event_key = form.get("event", "marriage")
    start_year = int(form.get("start_year", 2025))
    end_year = int(form.get("end_year", 2032))

    data = predict_event(ana, event_key, start_year, end_year)

    store_request({
        "type": "event", "name": person_name, "event": event_key,
        "date": body.date, "time": body.time, "place": body.place,
        "lat": body.lat, "lon": body.lon, "utc_offset": body.utc_offset,
        "start_year": start_year, "end_year": end_year,
    })

    ctx = {"request": request, "T": T, "lang": lang, "data": data, "person_name": person_name}
    return request.app.state.templates.TemplateResponse(request, name="partials/event_results.html", context=ctx)


# === Kundali History ===

@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(403, "लॉगिन आवश्यक आहे.")
    from ..firestore import get_kundali_records
    records = await get_kundali_records(user["uid"])
    ctx = _ctx(request, "history", records=records)
    return request.app.state.templates.TemplateResponse(request, name="pages/history.html", context=ctx)


@router.post("/history/{record_id}/regenerate/{pdf_type}", response_class=HTMLResponse)
async def history_regenerate(record_id: str, pdf_type: str, request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(403, "लॉगिन आवश्यक आहे.")
    from ..firestore import get_kundali_record, save_kundali_record
    from ..storage import upload_pdf
    from ..api.common import BirthInput, parse_birth
    from ..auth import ALL_FEATURES

    rec = await get_kundali_record(record_id)
    if not rec or rec.get("uid") != user["uid"]:
        from fastapi import HTTPException
        raise HTTPException(404, "नोंद सापडली नाही.")

    user_features = getattr(request.state, "user_features", None) or set(ALL_FEATURES)
    if f"pdf_{pdf_type}" not in user_features:
        from fastapi import HTTPException
        raise HTTPException(403, "परवानगी नाही.")

    profile = getattr(request.state, "profile", None)
    body = BirthInput(
        name=rec.get("person_name") or None,
        date=rec["birth_date"], time=rec["birth_time"],
        lat=rec.get("lat"), lon=rec.get("lon"),
        utc_offset=rec.get("utc_offset", 5.5),
        place=rec.get("place") or None,
    )
    birth = parse_birth(body)
    kwargs = dict(
        person_name=rec.get("person_name") or None,
        place_name=rec.get("place") or None,
        gender=rec.get("gender") or None,
        gotra=rec.get("gotra") or None,
        parents=rec.get("parents") or None,
        astrologer_name=profile.get("display_name", "") if profile else "",
        astrologer_credentials=profile.get("credentials", "") if profile else "",
    )

    import asyncio
    from functools import partial
    from ..pdf import generate_micro_mr_pdf, generate_mini_mr_pdf
    fn = partial(generate_micro_mr_pdf if pdf_type == "micro" else generate_mini_mr_pdf, birth, **kwargs)
    loop = asyncio.get_running_loop()
    pdf_bytes = await loop.run_in_executor(None, fn)

    url = await upload_pdf(user["uid"], record_id, pdf_type, pdf_bytes)
    await save_kundali_record(record_id, user["uid"], {f"pdf_{pdf_type}_url": url})

    return HTMLResponse(
        f'<a href="{url}" target="_blank" '
        f'class="inline-flex items-center gap-1 text-xs font-semibold text-green-600">'
        f'✓ पुन्हा तयार झाले — उघडा</a>'
    )


@router.delete("/history/{record_id}", response_class=HTMLResponse)
async def history_delete(record_id: str, request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(403)
    from ..firestore import get_kundali_record, delete_kundali_record
    from ..storage import delete_pdf

    rec = await get_kundali_record(record_id)
    if not rec or rec.get("uid") != user["uid"]:
        from fastapi import HTTPException
        raise HTTPException(404)

    await delete_kundali_record(record_id)
    for t in ("micro", "mini"):
        if rec.get(f"pdf_{t}_url"):
            await delete_pdf(user["uid"], record_id, t)

    return HTMLResponse("")  # HTMX swaps the row out


# === Janmanav Editor ===

def _require_janmanav_access(request: Request):
    from fastapi import HTTPException
    profile = getattr(request.state, "profile", None)
    is_admin = profile and profile.get("is_admin")
    user_features = getattr(request.state, "user_features", set())
    if not is_admin and "janmanav_editor" not in user_features:
        raise HTTPException(403, "जन्मनाव संपादनासाठी परवानगी नाही.")


@router.get("/janmanav", response_class=HTMLResponse)
async def janmanav_editor_page(request: Request):
    _require_janmanav_access(request)
    from ..firestore import get_all_janmanav
    from ...calc.constants import NAKSHATRAS
    from ..i18n import get_translator
    T = get_translator(settings.app.default_lang)
    entries = await get_all_janmanav()
    ctx = _ctx(request, "janmanav", entries=entries, T=T, NAKSHATRAS=NAKSHATRAS)
    return request.app.state.templates.TemplateResponse(request, name="pages/janmanav.html", context=ctx)


@router.post("/janmanav/{syllable}", response_class=HTMLResponse)
async def janmanav_save(syllable: str, request: Request):
    _require_janmanav_access(request)
    from ..firestore import update_janmanav_entry
    form = await request.form()
    m = form.get("m", "").strip()
    f = form.get("f", "").strip()
    if not m or not f:
        from fastapi import HTTPException
        raise HTTPException(400, "नाव रिकामे असू शकत नाही.")
    await update_janmanav_entry(syllable, m, f)
    return HTMLResponse(
        f'<span class="text-xs font-semibold text-green-600 saved-flash">✓ सेव झाले</span>'
    )
