"""Geocode API endpoint — city search/autocomplete via Nominatim."""

import logging
import urllib.request
import urllib.parse
import json

from fastapi import APIRouter, Query

from ...calc.geocode import lookup_city

logger = logging.getLogger("kundli.geocode")

router = APIRouter()

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _nominatim_search(query: str, limit: int = 5) -> list[dict]:
    """Search Nominatim for places matching the query."""
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": limit,
        "countrycodes": "in",
    })
    url = f"{_NOMINATIM_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Kundli/0.1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        logger.warning("Nominatim request failed: %s", e)
        return []


@router.get("/geocode/suggest")
def api_geocode_suggest(q: str = Query(..., min_length=2)):
    """Autocomplete endpoint — returns up to 5 place suggestions."""
    # Try local lookup first (instant, no network)
    exact = lookup_city(q)
    if exact:
        lat, lon, utc = exact
        return {"results": [{"name": q.strip().title(), "state": "", "lat": lat, "lon": lon, "utc_offset": utc}]}

    # Fall back to Nominatim
    raw = _nominatim_search(q, limit=10)
    results = []
    seen = set()
    for item in raw:
        addr = item.get("address", {})
        name = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet") or item.get("name", q)
        state = addr.get("state", "")
        district = addr.get("state_district") or addr.get("county", "")
        key = (name.lower(), state.lower())
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "name": name,
            "state": state,
            "district": district,
            "lat": round(float(item["lat"]), 4),
            "lon": round(float(item["lon"]), 4),
            "utc_offset": 5.5,
        })
        if len(results) >= 5:
            break

    return {"results": results}


# Keep the old endpoint for backwards compatibility
@router.get("/geocode")
def api_geocode(q: str = Query(..., min_length=2)):
    return api_geocode_suggest(q=q)
