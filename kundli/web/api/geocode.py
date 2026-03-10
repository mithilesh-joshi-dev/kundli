"""Geocode API endpoint — city search/autocomplete."""

from fastapi import APIRouter, Query

from ...calc.geocode import fuzzy_search, lookup_city

router = APIRouter()


@router.get("/geocode")
def api_geocode(q: str = Query(..., min_length=2)):
    exact = lookup_city(q)
    if exact:
        lat, lon, utc = exact
        return {"results": [{"name": q.title(), "lat": lat, "lon": lon, "utc_offset": utc}]}

    matches = fuzzy_search(q)
    return {
        "results": [
            {"name": name, "lat": lat, "lon": lon}
            for name, lat, lon in matches
        ]
    }
