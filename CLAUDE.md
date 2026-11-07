# CLAUDE.md — Kundli Project

## Architecture

**FastAPI + HTMX + Jinja2 + Tailwind**. No database — stateless calculation engine. Auth/user data via Firebase + Firestore.

- `kundli/calc/` — Pure Python calculation engine. All English internally. No side effects.
- `kundli/web/` — FastAPI app. Routes, auth middleware, PDF generation, i18n.
- `kundli/display/` — Rich terminal output for CLI only.
- `kundli/cli.py` — Typer CLI entry point.
- `kundli/config.py` — Single `Settings` singleton via env vars (`KUNDLI_*` prefix).

## Key Conventions

**Calc layer is English-only.** Never add Marathi/Hindi strings to `calc/`. Translations live in `kundli/web/i18n/{mr,hi,en}.py` only.

**i18n is server-side.** Use `T("key")` in templates. When adding a new translatable string, add the key to all three files: `mr.py`, `hi.py`, `en.py`.

**Default language is Marathi (`mr`).** Set via `KUNDLI_DEFAULT_LANG`.

**Chart style is North Indian diamond.** House-centric SVG, 300×300 viewBox.

**No `predict.py` or `events.py`** — these were deleted. Use `predict2.py` and `events2.py` instead.

## Calculation Entry Points

```python
from kundli.calc.engine import calculate_chart       # → Chart
from kundli.calc.analysis import build_analysis      # → ChartAnalysis
from kundli.calc.predict2 import generate_predictions # needs ChartAnalysis
from kundli.calc.events2 import predict_event        # event timing
```

Always call `build_analysis(chart)` before `generate_predictions` or `predict_event`.

## Auth & Access Control

- Auth: Firebase session cookie (`__session`)
- User profiles: Firestore `jyotishacharyas/{uid}`
- `request.state.user_features` — set of enabled features (resolved by `AuthMiddleware`)
- `features: None` in Firestore = legacy user (all features enabled)
- `features: []` = new user, no access until admin grants features
- Use `_require_feature(request, "feature_name")` in page routes to gate access

All features: `chart`, `predict`, `transit`, `match`, `questions`, `pdf_micro`, `pdf_mini`, `pdf_full`

## PDF Generation

- `generate_micro_mr_pdf(birth, ...)` — compact Marathi PDF (ReportLab)
- `generate_mini_mr_pdf(birth, ...)` — full Marathi PDF with chart (WeasyPrint + Jinja2)
- Templates: `kundli/web/templates/pdf/`
- **WeasyPrint SVG rule**: CSS classes do NOT reliably cascade into SVG children. Always use inline `fill=` and `stroke=` attributes on SVG elements.
- Singletons: `_jinja_env` and `_get_font_config()` are module-level to avoid re-loading on each request.
- PDF generation is offloaded to a thread pool: `loop.run_in_executor(None, fn)`

## Templates

- `base.html` — desktop nav, mobile bottom nav, Web Share API script
- Mobile bottom nav shows icons-only when 6+ items (avoids cramping)
- Main content has `pb-20 md:pb-0` to clear the fixed 56px mobile bottom nav
- HTMX partials are in `templates/partials/`
- PDF share button: forms with `data-pdf-share="filename.pdf"` are intercepted by JS on mobile; fallback to `target="_blank"` on desktop

## Deployment

- **Hosting**: Google Cloud Run (`asia-south1`), auto-deploys on push to `main`
- **min-instances=0** → scales to zero; cold start ~2–3s
- **Memory**: 512Mi, 1 CPU, max 2 instances
- Push to `main` → GitHub Action builds Docker image → deploys to Cloud Run

## Astrological Conventions

- Ayanamsha: Lahiri (Chitrapaksha) — `swe.SIDM_LAHIRI`
- House system: Whole Sign
- Planets: Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu (mean node), Ketu (Rahu+180°), Uranus, Neptune, Pluto
- Paya: Traditional grouping (NOT cyclic % 4 formula). See `NAKSHATRA_PAYA` in `constants.py`.
- Dasha: Vimshottari (120-year)
