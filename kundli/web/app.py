"""Kundli Web Application — FastAPI + HTMX + Jinja2."""

import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import settings
from .api import chart, geocode, matching, predict, transit
from .pages.router import router as pages_router

BASE_DIR = Path(__file__).parent

logger = logging.getLogger("kundli")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Kundli",
        version="0.1.0",
        description="Vedic Astrology Web Application",
        docs_url="/docs" if settings.app.debug else None,
        redoc_url=None,
    )

    # --- Middleware ---

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        elapsed = (time.monotonic() - start) * 1000
        logger.info(
            "%s %s %d %.0fms",
            request.method, request.url.path, response.status_code, elapsed,
        )
        return response

    # --- Error handlers ---

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        if _is_htmx(request):
            return _htmx_error_response("Something went wrong. Please try again.", 500)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if _is_htmx(request):
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            return _htmx_error_response(detail, exc.status_code)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        if _is_htmx(request):
            return _htmx_error_response(str(exc), 400)
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    # --- Templates & Static ---

    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    app.state.templates = templates

    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # --- Routes ---

    @app.get("/health")
    def health_check():
        return {"status": "ok", "version": "0.1.0"}

    app.include_router(chart.router, prefix="/api", tags=["chart"])
    app.include_router(predict.router, prefix="/api", tags=["predict"])
    app.include_router(transit.router, prefix="/api", tags=["transit"])
    app.include_router(matching.router, prefix="/api", tags=["matching"])
    app.include_router(geocode.router, prefix="/api", tags=["geocode"])
    app.include_router(pages_router)

    return app


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _htmx_error_response(message: str, status_code: int) -> HTMLResponse:
    """Return a styled HTML error fragment for HTMX requests."""
    from html import escape
    safe_msg = escape(message)
    html = (
        '<div class="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">'
        '<span class="text-red-500 text-lg leading-none mt-0.5">⚠</span>'
        '<div>'
        '<p class="text-sm font-medium text-red-800">Error</p>'
        f'<p class="text-sm text-red-600 mt-0.5">{safe_msg}</p>'
        '</div>'
        '</div>'
    )
    return HTMLResponse(content=html, status_code=status_code)


app = create_app()


def main():
    """Entry point for kundli-web command."""
    import uvicorn

    logging.basicConfig(
        level=getattr(logging, settings.server.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    uvicorn.run(
        "kundli.web.app:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
        workers=settings.server.workers if not settings.server.reload else 1,
        log_level=settings.server.log_level,
    )


if __name__ == "__main__":
    main()
