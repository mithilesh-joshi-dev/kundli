# ⚠️ DEPRECATED — This repository is no longer maintained

**This project has been superseded by [jyotishya](https://github.com/mithilesh-joshi-dev/jyotishya). Do not use this repo.**

---

# कुंडली — Vedic Astrology Platform

A professional Vedic astrology web application for Jyotishacharyas. Generates detailed birth charts (kundli) with Dasha, Transit, Ashtakavarga, predictions, and PDF reports in Marathi.

## Features

- **जन्म कुंडली** — North Indian diamond chart with full Panchang
- **भविष्यफल** — Dasha + Transit + Ashtakavarga combined predictions
- **गोचर** — Planetary transit analysis over time
- **कुंडली जुळवणी** — Ashtakoot Milan (36-point marriage compatibility)
- **प्रश्न** — Event timing for specific life questions (marriage, career, etc.)
- **PDF पत्रिका** — Marathi PDF reports (micro / mini formats) with Web Share API for mobile
- **Admin panel** — Feature-based access control, user approval

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Frontend | HTMX + Jinja2 + Tailwind CSS |
| Astro Engine | Swiss Ephemeris (pyswisseph) |
| PDF | WeasyPrint (Devanagari) |
| Auth | Firebase Auth + Firestore |
| Hosting | Google Cloud Run (asia-south1) |

## Project Structure

```
kundli/
├── calc/           # Pure calculation engine (stateless, English canonical)
│   ├── engine.py       # Main chart calculation entry point
│   ├── analysis.py     # ChartAnalysis — pre-computed strength/dignity
│   ├── predict2.py     # Prediction engine (Dasha + Transit + Ashtakavarga)
│   ├── events2.py      # Event timing / question answering
│   ├── dasha.py        # Vimshottari Dasha
│   ├── ashtakavarga.py # BAV/SAV calculation
│   ├── shadbala.py     # Shadbala + Vimshopaka
│   ├── vargas.py       # 16 divisional charts
│   ├── matching.py     # Ashtakoot Milan
│   ├── transit.py      # Gochar analysis
│   ├── panchang.py     # Tithi, Nakshatra, Vara, Yoga, Karana
│   ├── navamsa.py      # D9 chart
│   ├── yogas.py        # Yoga detection
│   ├── aspects.py      # Planetary aspects
│   ├── bhrigu.py       # Bhrigu Bindu
│   ├── constants.py    # PLANETS, RASHIS, NAKSHATRAS, PAYA, etc.
│   └── utils.py        # Shared helpers
│
├── web/            # FastAPI web application
│   ├── app.py          # App factory, middleware, exception handlers
│   ├── auth.py         # Firebase auth, session, feature access control
│   ├── pdf.py          # PDF generation (WeasyPrint + Jinja2)
│   ├── api/            # JSON API endpoints
│   └── pages/          # HTMX page routes
│       └── router.py
│
├── display/        # Rich terminal output (CLI only)
├── cli.py          # Typer CLI (chart, predict, transit, match, search)
├── config.py       # Settings via env vars (KUNDLI_* prefix)
└── models.py       # BirthData, Chart, PlanetPosition dataclasses
```

## Setup

### Prerequisites
- Python 3.10+
- Swiss Ephemeris data files
- Firebase project (Auth + Firestore)
- Google Cloud project (for Cloud Run deployment)

### Local Development

```bash
# Install dependencies
pip install -e .

# Set environment variables
export FIREBASE_API_KEY=...
export FIREBASE_AUTH_DOMAIN=...
export FIREBASE_PROJECT_ID=...
export FIREBASE_APP_ID=...
export GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Run dev server
kundli-web
# or
python -m kundli.web
```

Runs at `http://localhost:8000`. Docs at `/docs` (only when `KUNDLI_DEBUG=true`).

### CLI Usage

```bash
# Generate birth chart
kundli chart --date 1999-08-03 --time 14:30 --place Khamgaon

# Predictions
kundli predict --date 1999-08-03 --time 14:30 --place Khamgaon --from 2025 --to 2027

# Transit analysis
kundli transit --date 1999-08-03 --time 14:30 --place Khamgaon

# Kundli matching
kundli match --date1 1999-08-03 --time1 14:30 --place1 Khamgaon \
             --date2 1999-09-14 --time2 10:00 --place2 Amravati

# Search city
kundli search Nagpur
```

## Configuration

All settings via environment variables (prefix `KUNDLI_`):

| Variable | Default | Description |
|---|---|---|
| `KUNDLI_HOST` | `0.0.0.0` | Server host |
| `KUNDLI_PORT` | `8000` | Server port |
| `KUNDLI_RELOAD` | `false` | Auto-reload (dev only) |
| `KUNDLI_WORKERS` | `2` | Uvicorn workers |
| `KUNDLI_DEFAULT_LANG` | `mr` | Default UI language |
| `KUNDLI_DEBUG` | `false` | Enable /docs endpoint |

## Deployment

Deploys to **Google Cloud Run** on every push to `main` via GitHub Actions.

```bash
# Manual deploy
gcloud run deploy kundli --source=. --region=asia-south1
```

Health check: `GET /health`

## Astrological Notes

- **Ayanamsha**: Lahiri (Chitrapaksha)
- **House System**: Whole Sign
- **Planets**: Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu, Uranus, Neptune, Pluto
- **Dasha**: Vimshottari (120-year cycle)
- **Charts**: D1 (Rashi), D9 (Navamsa), plus 14 other divisional charts

## Access Control

Users are authenticated via Google (Firebase). The admin can:
- Approve / reject new users
- Enable/disable features per user: `chart`, `predict`, `transit`, `match`, `questions`, `pdf_micro`, `pdf_mini`, `pdf_full`

Admin panel: `/admin` (admin users only)
