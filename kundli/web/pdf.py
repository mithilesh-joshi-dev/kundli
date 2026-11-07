"""Kundli PDF report generator.

Report tiers:
  micro — portrait postcard 4"×6", text-only (janmanav, nakshatra, panchang, dasha)
  mini  — TODO: portrait/landscape with North Indian chart
  full  — TODO: multi-page complete report

Rendering:
  English (lang=en) → reportlab
  Marathi  (lang=mr) → WeasyPrint (HTML→PDF, Pango shaping for Devanagari)
"""

import os
import sys
from datetime import datetime, date
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas

from ..calc.constants import (
    NAKSHATRA_LORDS, NAKSHATRAS,
    NAKSHATRA_GANA, NAKSHATRA_YONI, NAKSHATRA_JANMAKSHARA,
    NAKSHATRA_PAYA,
    RASHI_VARNA, RASHI_LORD, PLANET_RATNA,
)
from ..calc.dasha import calculate_dasha
from ..calc.engine import calculate_chart
from ..calc.panchang import calculate_panchang
from ..models import BirthData
from .i18n import get_translator

_PDF_TEMPLATE_DIR = Path(__file__).parent / "templates" / "pdf"

# ── Module-level singletons (created once, reused across all requests) ────────

# Jinja2 env: compiled templates are cached in-process — avoids re-parsing
# and re-compiling the template bytecode on every PDF request.
from jinja2 import Environment, FileSystemLoader as _FSL  # noqa: E402
_jinja_env = Environment(loader=_FSL(str(_PDF_TEMPLATE_DIR)))

# WeasyPrint FontConfiguration: holds the loaded font data and Pango font map.
# NotoSerifDevanagari is large; loading it on every request adds ~300-600 ms.
# Initialised lazily on first PDF call so the app starts fast.
_font_config = None


def _get_font_config():
    global _font_config
    if _font_config is None:
        try:
            from weasyprint.text.fonts import FontConfiguration  # noqa: PLC0415
            _font_config = FontConfiguration()
        except Exception:
            pass
    return _font_config

# ── Marathi panchang translation dicts ───────────────────────────────────────

_MR_PAKSHA = {"Shukla": "शुक्ल", "Krishna": "कृष्ण"}

_MR_TITHI = {
    "Pratipada": "प्रतिपदा", "Dwitiya": "द्वितीया", "Tritiya": "तृतीया",
    "Chaturthi": "चतुर्थी", "Panchami": "पंचमी", "Shashthi": "षष्ठी",
    "Saptami": "सप्तमी", "Ashtami": "अष्टमी", "Navami": "नवमी",
    "Dashami": "दशमी", "Ekadashi": "एकादशी", "Dwadashi": "द्वादशी",
    "Trayodashi": "त्रयोदशी", "Chaturdashi": "चतुर्दशी",
    "Purnima": "पौर्णिमा", "Amavasya": "अमावास्या",
}

_MR_YOGA = {
    "Vishkambha": "विष्कंभ", "Priti": "प्रीति", "Ayushman": "आयुष्मान",
    "Saubhagya": "सौभाग्य", "Shobhana": "शोभन", "Atiganda": "अतिगंड",
    "Sukarma": "सुकर्म", "Dhriti": "धृति", "Shoola": "शूल",
    "Ganda": "गंड", "Vriddhi": "वृद्धि", "Dhruva": "ध्रुव",
    "Vyaghata": "व्याघात", "Harshana": "हर्षण", "Vajra": "वज्र",
    "Siddhi": "सिद्धि", "Vyatipata": "व्यतिपात", "Variyana": "वरीयान",
    "Parigha": "परिघ", "Shiva": "शिव", "Siddha": "सिद्ध",
    "Sadhya": "साध्य", "Shubha": "शुभ", "Shukla": "शुक्ल",
    "Brahma": "ब्रह्म", "Mahendra": "महेंद्र", "Vaidhriti": "वैधृति",
}

_MR_KARANA = {
    "Bava": "बव", "Balava": "बालव", "Kaulava": "कौलव",
    "Taitila": "तैतिल", "Gara": "गर", "Vanija": "वणिज",
    "Vishti": "विष्टि", "Shakuni": "शकुनि", "Chatushpada": "चतुष्पाद",
    "Nagava": "नागव", "Kimstughna": "किंस्तुघ्न",
}

_MR_MONTHS_SHORT = [
    "जाने", "फेब्रु", "मार्च", "एप्रि", "मे", "जून",
    "जुलै", "ऑग", "सप्टे", "ऑक्टो", "नोव्हें", "डिसें",
]

_MR_GANA = {"Deva": "देव गण", "Manushya": "मनुष्य गण", "Rakshasa": "राक्षस गण"}
_MR_YONI = {
    "Ashwa": "अश्व", "Gaja": "गज", "Mesha": "मेष", "Sarpa": "सर्प",
    "Shwaan": "श्वान", "Marjara": "मार्जार", "Mushika": "मूषिक",
    "Go": "गो", "Mahisha": "महिष", "Vyaghra": "व्याघ्र",
    "Mriga": "मृग", "Vanara": "वानर", "Nakula": "नकुळ", "Simha": "सिंह",
}
_MR_NADI = {0: "आदि नाडी", 1: "मध्य नाडी", 2: "अंत्य नाडी"}
_MR_VARNA = {
    "Brahmin": "ब्राह्मण वर्ण", "Kshatriya": "क्षत्रिय वर्ण",
    "Vaishya": "वैश्य वर्ण", "Shudra": "शूद्र वर्ण",
}
_MR_RASHI_LORD = {
    "Sun": "सूर्य", "Moon": "चंद्र", "Mars": "मंगळ",
    "Mercury": "बुध", "Jupiter": "गुरू (बृहस्पती)",
    "Venus": "शुक्र", "Saturn": "शनि",
}
_MR_RATNA = {
    "Manik": "माणिक", "Moti": "मोती", "Munga": "मुंगा",
    "Panna": "पाचू", "Pushkaraj": "पुष्कराज", "Heera": "हिरा",
    "Neelam": "नीलम", "Gomed": "गोमेद", "Lahsuniya": "लहसुनिया",
}
_MR_PAYA = {
    "Swarna": "सोन्याचा पाय",
    "Rajat":  "रुप्याचा पाय",
    "Tamra":  "तांब्याचा पाय",
    "Loh":    "लोखंडाचा पाय",
}

_MR_PLANET_SHORT = {
    "Sun": "सू", "Moon": "चं", "Mars": "मं", "Mercury": "बु",
    "Jupiter": "गु", "Venus": "शु", "Saturn": "श", "Rahu": "रा", "Ketu": "के",
    "Uranus": "यु", "Neptune": "ने", "Pluto": "प्लु",
}

_MR_VARA = {
    "Sunday": "रविवार", "Monday": "सोमवार", "Tuesday": "मंगळवार",
    "Wednesday": "बुधवार", "Thursday": "गुरुवार", "Friday": "शुक्रवार",
    "Saturday": "शनिवार",
}

# North Indian diamond house geometry (300×300 viewBox)
_NI_HOUSES = {
    1:  {"points": "150,0 225,75 150,150 75,75",    "cx": 150, "cy": 68,  "nx": 150, "ny": 28},
    2:  {"points": "0,0 150,0 75,75",               "cx": 75,  "cy": 22,  "nx": 60,  "ny": 15},
    3:  {"points": "0,0 75,75 0,150",               "cx": 22,  "cy": 68,  "nx": 12,  "ny": 28},
    4:  {"points": "75,75 150,150 75,225 0,150",    "cx": 75,  "cy": 150, "nx": 32,  "ny": 115},
    5:  {"points": "0,300 0,150 75,225",             "cx": 22,  "cy": 228, "nx": 12,  "ny": 268},
    6:  {"points": "150,300 0,300 75,225",           "cx": 75,  "cy": 278, "nx": 60,  "ny": 288},
    7:  {"points": "150,300 75,225 150,150 225,225", "cx": 150, "cy": 232, "nx": 150, "ny": 278},
    8:  {"points": "300,300 150,300 225,225",        "cx": 225, "cy": 278, "nx": 240, "ny": 288},
    9:  {"points": "300,150 300,300 225,225",        "cx": 278, "cy": 228, "nx": 288, "ny": 268},
    10: {"points": "225,75 300,150 225,225 150,150", "cx": 225, "cy": 150, "nx": 268, "ny": 115},
    11: {"points": "300,0 300,150 225,75",           "cx": 278, "cy": 68,  "nx": 288, "ny": 28},
    12: {"points": "150,0 300,0 225,75",             "cx": 225, "cy": 22,  "nx": 240, "ny": 15},
}


def _build_ni_chart_data(planets_in_houses: dict[int, list[str]], lagna_rashi_idx: int, T) -> list[dict]:
    """Build house data list for the North Indian chart SVG."""
    from ..calc.constants import RASHIS
    houses = []
    for h in range(1, 13):
        rashi = RASHIS[(lagna_rashi_idx + h - 1) % 12]
        geo = _NI_HOUSES[h]
        houses.append({
            "number": h,
            "rashi_local": T(f"rashi.{rashi}"),
            "planets": planets_in_houses.get(h, []),
            **geo,
        })
    return houses


def _to_dev(text) -> str:
    """Convert ASCII digits in a string to Devanagari numerals."""
    return str(text).translate(str.maketrans("0123456789", "०१२३४५६७८९"))


def _maha_duration_mr(start, end) -> str:
    """Format mahadasha remaining duration as 'X वर्षे, Y महिने'."""
    total_months = (end.year - start.year) * 12 + (end.month - start.month)
    years, months = total_months // 12, total_months % 12
    parts = []
    if years:
        parts.append(f"{_to_dev(years)} वर्षे")
    if months:
        parts.append(f"{_to_dev(months)} महिने")
    return ", ".join(parts) if parts else "—"


def _mr_tithi(s: str) -> str:
    parts = s.split(" ", 1)
    if len(parts) == 2:
        return f"{_MR_PAKSHA.get(parts[0], parts[0])} {_MR_TITHI.get(parts[1], parts[1])}"
    return s


def _mr_month_year(dt) -> str:
    return f"{_MR_MONTHS_SHORT[dt.month - 1]} {dt.year}"


def _weasyprint_html():
    """Lazy-load WeasyPrint, setting macOS Homebrew library path first."""
    if sys.platform == "darwin":
        brew = "/opt/homebrew/lib"
        dyld = os.environ.get("DYLD_LIBRARY_PATH", "")
        if brew not in dyld:
            os.environ["DYLD_LIBRARY_PATH"] = f"{brew}:{dyld}".strip(":")
    from weasyprint import HTML  # noqa: PLC0415
    return HTML

# ── Page sizes ────────────────────────────────────────────────────────────────
MICRO_W = 4 * inch   # 288 pt  (portrait 4"×6")
MICRO_H = 6 * inch   # 432 pt

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# ── Colour palette ────────────────────────────────────────────────────────────
# Primary
_MAROON      = colors.HexColor("#7B1D1D")   # header bg, lagna, mahadasha
_GOLD        = colors.HexColor("#B8860B")   # border, divider lines
_GOLD_LIGHT  = colors.HexColor("#FDF0CC")   # header subtitle text
_AMBER       = colors.HexColor("#D97706")   # section badge text + dot
_AMBER_BG    = colors.HexColor("#FFF6E0")   # section badge background

# Page
_PAGE_BG     = colors.HexColor("#FEFAF0")   # warm ivory

# Text
_TEXT_DARK   = colors.HexColor("#1C0A00")   # near-black warm (main values)
_TEXT_MID    = colors.HexColor("#78350F")   # warm brown (row labels)
_TEXT_SUBTLE = colors.HexColor("#A16207")   # subtitle / ayanamsha

# Value colours
_LAGNA_C     = colors.HexColor("#7B1D1D")   # maroon — lagna
_MOON_C      = colors.HexColor("#1E3A8A")   # deep navy — moon rashi
_NAK_C       = colors.HexColor("#14532D")   # deep green — nakshatra

# Separators
_SEP_GOLD    = colors.HexColor("#D4AF37")   # outer border / strong sep
_SEP_THIN    = colors.HexColor("#E8D5A3")   # inner thin dividers


# ── Shared draw helpers ───────────────────────────────────────────────────────

def _hsep(c, x1, x2, y, col=_SEP_THIN, lw=0.4):
    c.setStrokeColor(col)
    c.setLineWidth(lw)
    c.line(x1, y, x2, y)


def _badge(c, x, y, text, page_w, M):
    """Amber pill section heading with a leading dot."""
    tw = c.stringWidth(text, "Helvetica-Bold", 7)
    bw = tw + 20          # padding: 8 left (3 margin + 5 for dot+gap) + 9 right
    bh = 13
    c.setFillColor(_AMBER_BG)
    c.roundRect(M, y - 2, bw, bh, 3, fill=1, stroke=0)
    # amber dot
    c.setFillColor(_AMBER)
    c.circle(M + 7, y + 4.5, 2.2, fill=1, stroke=0)
    # text
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(_AMBER)
    c.drawString(M + 13, y, text.upper())


def _row(c, x, y, label, value,
         lc=_TEXT_MID, vc=_TEXT_DARK,
         lsz=7.5, vsz=9, lw=100):
    """Single label → value row."""
    c.setFont("Helvetica", lsz)
    c.setFillColor(lc)
    c.drawString(x, y, label)
    c.setFont("Helvetica-Bold", vsz)
    c.setFillColor(vc)
    c.drawString(x + lw, y, str(value))


def _two_col(c, x, y, l1, v1, l2, v2, gap=129, lw=42, lsz=7.5, vsz=8.5):
    """Two label→value pairs side by side."""
    for lbl, val, ox in ((l1, v1, 0), (l2, v2, gap)):
        c.setFont("Helvetica", lsz)
        c.setFillColor(_TEXT_MID)
        c.drawString(x + ox, y, lbl)
        c.setFont("Helvetica-Bold", vsz)
        c.setFillColor(_TEXT_DARK)
        c.drawString(x + ox + lw, y, str(val))


# ── Micro PDF (portrait, text-only) ──────────────────────────────────────────

def generate_micro_pdf(
    birth: BirthData,
    person_name: str | None = None,
    place_name: str | None = None,
) -> bytes:
    """Return PDF bytes for a portrait 4"×6" Janma Kundali micro card."""
    chart = calculate_chart(birth)
    b = birth

    panchang = calculate_panchang(
        b.year, b.month, b.day, b.hour, b.minute, b.second, b.utc_offset
    )

    # Active Mahadasha + Antardasha
    now = datetime.now()
    maha_lord = maha_start = maha_end = None
    antar_lord = antar_start = antar_end = None
    for lord, start, end, antardashas in calculate_dasha(chart):
        if start <= now < end:
            maha_lord, maha_start, maha_end = lord, start, end
            for al, a_start, a_end in antardashas:
                if a_start <= now < a_end:
                    antar_lord, antar_start, antar_end = al, a_start, a_end
                    break
            break

    moon = next((p for p in chart.planets if p.name == "Moon"), None)
    lagna = chart.lagna
    nak_lord = None
    if moon and moon.nakshatra in NAKSHATRAS:
        nak_lord = NAKSHATRA_LORDS[NAKSHATRAS.index(moon.nakshatra)]

    buf = BytesIO()
    w, h = MICRO_W, MICRO_H   # 288 × 432
    M = 16                     # content margin

    c = rl_canvas.Canvas(buf, pagesize=(w, h))

    # ── Page background ───────────────────────────────────────────────────────
    c.setFillColor(_PAGE_BG)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Outer double border
    c.setStrokeColor(_SEP_GOLD)
    c.setLineWidth(1.2)
    c.rect(5, 5, w - 10, h - 10, fill=0, stroke=1)
    c.setLineWidth(0.4)
    c.rect(8, 8, w - 16, h - 16, fill=0, stroke=1)

    # ── Header ────────────────────────────────────────────────────────────────
    HEADER_H = 36
    hy = h - HEADER_H          # = 396

    c.setFillColor(_MAROON)
    c.rect(0, hy, w, HEADER_H, fill=1, stroke=0)

    # Thin gold strip at bottom of header
    c.setFillColor(_SEP_GOLD)
    c.rect(0, hy, w, 1.5, fill=1, stroke=0)

    # Header text: title
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor("#D4AF37"))
    c.drawString(M, hy + 18, "JANMA KUNDALI")

    # Subtitle in lighter gold
    c.setFont("Helvetica", 7.5)
    c.setFillColor(_GOLD_LIGHT)
    c.drawString(M, hy + 7, "Vedic Birth Chart  •  Lahiri Ayanamsha")

    # Date top-right
    c.setFont("Helvetica", 7)
    c.setFillColor(_GOLD_LIGHT)
    c.drawRightString(w - M, hy + 20, date.today().strftime("%d %b %Y"))

    # ── Cursor (top-down through content) ────────────────────────────────────
    cur = hy - 10              # 386

    # ── Name block ────────────────────────────────────────────────────────────
    if person_name:
        c.setFont("Helvetica-Bold", 15)
        c.setFillColor(_TEXT_DARK)
        c.drawString(M, cur, person_name)
        cur -= 16

    c.setFont("Helvetica", 7.5)
    c.setFillColor(_TEXT_SUBTLE)
    c.drawString(M, cur, "Whole Sign Houses  •  Vimshottari Dasha")
    cur -= 9

    # Gold decorative line under name
    _hsep(c, M, w - M, cur, col=_SEP_GOLD, lw=0.7)
    cur -= 11

    # ── Section 1: Janmanav ───────────────────────────────────────────────────
    _badge(c, M, cur, "Janmanav  —  Birth Details", w, M)
    cur -= 16

    LINE = 13

    birth_date = f"{b.day:02d} {_MONTHS[b.month - 1]} {b.year}"
    _row(c, M, cur, "Date of Birth", birth_date)
    cur -= LINE

    h12 = b.hour % 12 or 12
    am = "AM" if b.hour < 12 else "PM"
    sign = "+" if b.utc_offset >= 0 else ""
    time_str = f"{h12}:{b.minute:02d} {am}  ·  UTC{sign}{b.utc_offset:g}"
    _row(c, M, cur, "Time of Birth", time_str)
    cur -= LINE

    place_str = place_name if place_name else f"{b.latitude:.3f}°N,  {b.longitude:.3f}°E"
    _row(c, M, cur, "Birth Place", place_str)
    cur -= LINE + 5

    _hsep(c, M, w - M, cur)
    cur -= 11

    # ── Section 2: Rashi & Nakshatra ─────────────────────────────────────────
    _badge(c, M, cur, "Rashi  —  Nakshatra", w, M)
    cur -= 16

    _row(c, M, cur, "Lagna (Ascendant)", lagna.rashi, vc=_LAGNA_C)
    cur -= LINE

    if moon:
        _row(c, M, cur, "Moon Rashi", moon.rashi, vc=_MOON_C)
        cur -= LINE

        _row(c, M, cur, "Janma Nakshatra", moon.nakshatra, vc=_NAK_C)
        cur -= LINE

        _row(c, M, cur, "Charan (Pada)", str(moon.nakshatra_pada))
        cur -= LINE

    if nak_lord:
        _row(c, M, cur, "Nakshatra Lord", nak_lord)
        cur -= LINE

    cur -= 5
    _hsep(c, M, w - M, cur)
    cur -= 11

    # ── Section 3: Panchang ──────────────────────────────────────────────────
    _badge(c, M, cur, "Panchang", w, M)
    cur -= 16

    # Two-column layout: (Tithi, Vara) and (Yoga, Karana)
    _two_col(c, M, cur,
             "Tithi", str(panchang["tithi"]),
             "Vara", panchang["vara"].title())
    cur -= LINE

    _two_col(c, M, cur,
             "Yoga", panchang["yoga"],
             "Karana", panchang["karana"])
    cur -= LINE

    # Ayanamsha — small, secondary info
    _row(c, M, cur, "Ayanamsha (Lahiri)",
         f"{chart.ayanamsha_value:.4f}°",
         lc=colors.HexColor("#B45309"),
         vc=_TEXT_SUBTLE, lsz=7, vsz=8)
    cur -= LINE + 5

    _hsep(c, M, w - M, cur)
    cur -= 11

    # ── Section 4: Dasha ─────────────────────────────────────────────────────
    _badge(c, M, cur, "Dasha  —  Current Period", w, M)
    cur -= 16

    if maha_lord:
        # Sub-label
        c.setFont("Helvetica", 6.5)
        c.setFillColor(_TEXT_MID)
        c.drawString(M, cur, "MAHADASHA")
        cur -= 12

        # Planet name — large and prominent
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(_MAROON)
        c.drawString(M, cur, maha_lord.upper())

        # Year range inline
        maha_w = c.stringWidth(maha_lord.upper(), "Helvetica-Bold", 14)
        c.setFont("Helvetica", 8.5)
        c.setFillColor(_TEXT_SUBTLE)
        c.drawString(M + maha_w + 7, cur + 1,
                     f"{maha_start.year} – {maha_end.year}")
        cur -= 15

    if antar_lord:
        c.setFont("Helvetica", 6.5)
        c.setFillColor(_TEXT_MID)
        c.drawString(M, cur, "ANTARDASHA")
        cur -= 12

        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(_TEXT_DARK)
        c.drawString(M, cur, antar_lord.upper())

        antar_w = c.stringWidth(antar_lord.upper(), "Helvetica-Bold", 11)
        if antar_start and antar_end:
            antar_dates = (
                f"{antar_start.strftime('%b %Y')} – "
                f"{antar_end.strftime('%b %Y')}"
            )
            c.setFont("Helvetica", 7.5)
            c.setFillColor(_TEXT_SUBTLE)
            c.drawString(M + antar_w + 7, cur + 1, antar_dates)
        cur -= 14

    # ── Footer ────────────────────────────────────────────────────────────────
    _hsep(c, M, w - M, 22, col=_SEP_GOLD, lw=0.7)

    c.setFont("Helvetica", 7)
    c.setFillColor(_TEXT_SUBTLE)
    c.drawCentredString(w / 2, 12, "✶   ✶   ✶")

    c.save()
    return buf.getvalue()


# ── Marathi micro PDF (WeasyPrint HTML→PDF) ───────────────────────────────────

def _collect_data(birth: BirthData):
    """Shared data extraction used by all PDF tiers."""
    chart = calculate_chart(birth)
    b = birth

    panchang = calculate_panchang(
        b.year, b.month, b.day, b.hour, b.minute, b.second, b.utc_offset
    )
    now = datetime.now()
    maha_lord = maha_start = maha_end = None
    antar_lord = antar_start = antar_end = None
    for lord, start, end, antardashas in calculate_dasha(chart):
        if start <= now < end:
            maha_lord, maha_start, maha_end = lord, start, end
            for al, a_start, a_end in antardashas:
                if a_start <= now < a_end:
                    antar_lord, antar_start, antar_end = al, a_start, a_end
                    break
            break

    moon = next((p for p in chart.planets if p.name == "Moon"), None)
    nak_lord = None
    if moon and moon.nakshatra in NAKSHATRAS:
        nak_lord = NAKSHATRA_LORDS[NAKSHATRAS.index(moon.nakshatra)]

    return dict(
        chart=chart, b=b, panchang=panchang, moon=moon, nak_lord=nak_lord,
        maha_lord=maha_lord, maha_start=maha_start, maha_end=maha_end,
        antar_lord=antar_lord, antar_start=antar_start, antar_end=antar_end,
    )


def generate_micro_mr_pdf(
    birth: BirthData,
    person_name: str | None = None,
    place_name: str | None = None,
    gender: str | None = None,
    gotra: str | None = None,
    parents: str | None = None,
    astrologer_name: str | None = None,
    astrologer_credentials: str | None = None,
) -> bytes:
    """Return PDF bytes — Marathi portrait micro card via WeasyPrint."""
    d = _collect_data(birth)
    b = d["b"]
    chart = d["chart"]
    panchang = d["panchang"]
    moon = d["moon"]

    T = get_translator("mr")

    # Translated values
    lagna_rashi_mr = T(f"rashi.{chart.lagna.rashi}")
    moon_rashi_mr  = T(f"rashi.{moon.rashi}") if moon else "—"
    nakshatra      = T(f"nakshatra.{moon.nakshatra}") if moon else "—"
    charan         = str(moon.nakshatra_pada) if moon else "—"
    nak_lord_name  = T(f"planet.{d['nak_lord']}") if d["nak_lord"] else "—"
    vara_mr        = T(f"vara.{panchang['vara']}")

    # Birth date/time
    mr_months = [
        "जानेवारी", "फेब्रुवारी", "मार्च", "एप्रिल", "मे", "जून",
        "जुलै", "ऑगस्ट", "सप्टेंबर", "ऑक्टोबर", "नोव्हेंबर", "डिसेंबर",
    ]
    birth_date = f"{b.day:02d} {mr_months[b.month - 1]} {b.year}"
    h12 = b.hour % 12 or 12
    am = "सकाळी" if b.hour < 12 else "संध्याकाळी"
    birth_time_short = f"{h12:02d}:{b.minute:02d} {am}"

    # Dasha names in Marathi
    maha_name  = T(f"planet.{d['maha_lord']}")  if d["maha_lord"]  else "—"
    antar_name = T(f"planet.{d['antar_lord']}") if d["antar_lord"] else "—"
    maha_years = (
        f"{d['maha_start'].year} – {d['maha_end'].year}"
        if d["maha_start"] else ""
    )
    antar_dates = (
        f"{_mr_month_year(d['antar_start'])} – {_mr_month_year(d['antar_end'])}"
        if d["antar_start"] else ""
    )

    # ── New derived fields ────────────────────────────────────────────────────

    # Nakshatra index
    nak_idx = NAKSHATRAS.index(moon.nakshatra) if moon and moon.nakshatra in NAKSHATRAS else None

    # Gana / Yoni
    gana_mr = _MR_GANA.get(NAKSHATRA_GANA[nak_idx], "—") if nak_idx is not None else "—"
    yoni_mr = _MR_YONI.get(NAKSHATRA_YONI[nak_idx], "—") if nak_idx is not None else "—"

    # Nadi (index % 3)
    nadi_mr = _MR_NADI.get(nak_idx % 3, "—") if nak_idx is not None else "—"

    # Varna (from moon rashi)
    varna_mr = _MR_VARNA.get(RASHI_VARNA.get(moon.rashi, ""), "—") if moon else "—"

    # Janmakshara (all 4 syllables for the nakshatra)
    if nak_idx is not None:
        syllables = NAKSHATRA_JANMAKSHARA[nak_idx]
        janmakshara = ", ".join(syllables)
        pada_syllable = syllables[moon.nakshatra_pada - 1] if moon else "—"
    else:
        janmakshara = "—"
        pada_syllable = "—"

    # Sun rashi
    sun = next((p for p in chart.planets if p.name == "Sun"), None)
    sun_rashi_mr = T(f"rashi.{sun.rashi}") if sun else "—"

    # Moon rashi lord and gemstone
    moon_rashi_lord = RASHI_LORD.get(moon.rashi, "") if moon else ""
    rashi_swami_mr = _MR_RASHI_LORD.get(moon_rashi_lord, moon_rashi_lord)
    ratna_key = PLANET_RATNA.get(moon_rashi_lord, "")
    ratna_mr = _MR_RATNA.get(ratna_key, ratna_key)

    # Paya (metal) from Moon nakshatra
    paya_mr = _MR_PAYA.get(NAKSHATRA_PAYA[nak_idx], "—") if nak_idx is not None else "—"

    # Lagna rashi (already computed above as lagna_rashi_mr)

    # Mahadasha duration
    maha_duration = _maha_duration_mr(d["maha_start"], d["maha_end"]) if d["maha_start"] else ""

    # Lat/lon in Devanagari numerals
    lat_str = _to_dev(f"{abs(b.latitude):.4f}") + ("° N" if b.latitude >= 0 else "° S")
    lon_str = _to_dev(f"{abs(b.longitude):.4f}") + ("° E" if b.longitude >= 0 else "° W")
    latlon = f"{lat_str}, {lon_str}"

    # Birth date/time in Devanagari numerals
    birth_date_dev = _to_dev(birth_date)
    birth_time_dev = _to_dev(birth_time_short)

    tmpl = _jinja_env.get_template("micro_mr.html")
    html_str = tmpl.render(
        today=date.today().strftime("%d %b %Y"),
        person_name=person_name or "",
        birth_date=birth_date,
        birth_date_dev=birth_date_dev,
        birth_time_short=birth_time_short,
        birth_time_dev=birth_time_dev,
        place=place_name or f"{b.latitude:.3f}°N, {b.longitude:.3f}°E",
        lagna_rashi=lagna_rashi_mr,
        moon_rashi=moon_rashi_mr,
        nakshatra=nakshatra,
        charan=charan,
        nak_lord=nak_lord_name,
        tithi=_mr_tithi(panchang["tithi"]),
        vara=vara_mr,
        yoga=_MR_YOGA.get(panchang["yoga"], panchang["yoga"]),
        karana=_MR_KARANA.get(panchang["karana"], panchang["karana"]),
        ayanamsha=f"{chart.ayanamsha_value:.4f}",
        maha_lord=maha_name,
        maha_years=maha_years,
        maha_duration=maha_duration,
        antar_lord=antar_name,
        antar_dates=antar_dates,
        # New fields
        gender=gender or "—",
        gotra=gotra or "—",
        parents=parents or "—",
        gana_yoni=f"{gana_mr} / {yoni_mr}",
        nadi_varna=f"{nadi_mr} / {varna_mr}",
        paya=paya_mr,
        janmakshara=janmakshara,
        sun_moon_rashi=f"{sun_rashi_mr} / {moon_rashi_mr}",
        rashi_swami_ratna=f"{rashi_swami_mr} / {ratna_mr}",
        latlon=latlon,
        astrologer_name=astrologer_name or "",
        astrologer_credentials=astrologer_credentials or "",
    )

    HTML = _weasyprint_html()
    return HTML(string=html_str, base_url=str(_PDF_TEMPLATE_DIR)).write_pdf(
        font_config=_get_font_config()
    )


# ── Mini Janma Patrika (micro details + D1 chart) ────────────────────────────

def generate_mini_mr_pdf(
    birth: BirthData,
    person_name: str | None = None,
    place_name: str | None = None,
    gender: str | None = None,
    gotra: str | None = None,
    parents: str | None = None,
    astrologer_name: str | None = None,
    astrologer_credentials: str | None = None,
) -> bytes:
    """Mini Janma Patrika: all micro fields + D1 chart. Custom ~A5 size."""
    T = get_translator("mr")
    chart   = calculate_chart(birth)
    panchang = calculate_panchang(
        birth.year, birth.month, birth.day,
        birth.hour, birth.minute, birth.second, birth.utc_offset,
    )
    all_dasha = calculate_dasha(chart)

    moon  = next((p for p in chart.planets if p.name == "Moon"), None)
    sun   = next((p for p in chart.planets if p.name == "Sun"),  None)
    lagna = chart.lagna
    lagna_rashi_idx = int(lagna.longitude / 30) % 12

    # D1 chart data
    d1_houses: dict[int, list[str]] = {i: [] for i in range(1, 13)}
    for p in chart.planets:
        d1_houses[p.house].append(_MR_PLANET_SHORT.get(p.name, p.name[:2]))
    d1_chart = _build_ni_chart_data(d1_houses, lagna_rashi_idx, T)

    # Nakshatra attrs
    nak_idx  = NAKSHATRAS.index(moon.nakshatra) if moon and moon.nakshatra in NAKSHATRAS else None
    gana_mr  = _MR_GANA.get(NAKSHATRA_GANA[nak_idx], "—") if nak_idx is not None else "—"
    yoni_mr  = _MR_YONI.get(NAKSHATRA_YONI[nak_idx], "—") if nak_idx is not None else "—"
    nadi_mr  = _MR_NADI.get(nak_idx % 3, "—") if nak_idx is not None else "—"
    varna_mr = _MR_VARNA.get(RASHI_VARNA.get(moon.rashi, ""), "—") if moon else "—"
    paya_mr  = _MR_PAYA.get(NAKSHATRA_PAYA[nak_idx], "—") if nak_idx is not None else "—"
    janmakshara = ", ".join(NAKSHATRA_JANMAKSHARA[nak_idx]) if nak_idx is not None else "—"

    moon_rashi_lord = RASHI_LORD.get(moon.rashi, "") if moon else ""
    rashi_swami_mr  = _MR_RASHI_LORD.get(moon_rashi_lord, moon_rashi_lord)
    ratna_mr        = _MR_RATNA.get(PLANET_RATNA.get(moon_rashi_lord, ""), "—")
    lagna_rashi_mr  = T(f"rashi.{lagna.rashi}") if lagna else "—"
    moon_rashi_mr   = T(f"rashi.{moon.rashi}") if moon else "—"
    sun_rashi_mr    = T(f"rashi.{sun.rashi}") if sun else "—"
    moon_nak_mr     = T(f"nakshatra.{moon.nakshatra}") if moon else "—"

    # Current maha + current antar only
    from datetime import datetime as dt
    now = dt.now()
    maha_lord_mr = maha_range = antar_lord_mr = antar_range = "—"
    for maha_lord, maha_start, maha_end, antars in all_dasha:
        if maha_start <= now <= maha_end:
            maha_lord_mr = T(f"planet.{maha_lord}")
            maha_range   = (
                f"{_to_dev(str(maha_start.year))} – {_to_dev(str(maha_end.year))}"
            )
            for a_lord, a_start, a_end in antars:
                if a_start <= now <= a_end:
                    antar_lord_mr = T(f"planet.{a_lord}")
                    antar_range   = (
                        f"{_to_dev(_MR_MONTHS_SHORT[a_start.month-1])} {_to_dev(str(a_start.year))} – "
                        f"{_to_dev(_MR_MONTHS_SHORT[a_end.month-1])} {_to_dev(str(a_end.year))}"
                    )
                    break
            break

    # Panchang
    paksha     = _MR_PAKSHA.get(panchang["paksha"], panchang["paksha"])
    tithi_name = panchang["tithi"].split(" ", 1)[-1]
    tithi_mr   = f"{paksha} {_MR_TITHI.get(tithi_name, tithi_name)}"
    vara_mr    = _MR_VARA.get(panchang["vara"], panchang["vara"])
    yoga_mr    = _MR_YOGA.get(panchang["yoga"], panchang["yoga"])
    karana_mr  = _MR_KARANA.get(panchang["karana"], panchang["karana"])

    birth_date_dev = _to_dev(f"{birth.day:02d}/{birth.month:02d}/{birth.year}")
    birth_time_dev = _to_dev(f"{birth.hour:02d}:{birth.minute:02d}")
    lat = getattr(birth, "latitude", None)
    lon = getattr(birth, "longitude", None)
    latlon = (
        f"{_to_dev(f'{abs(lat):.2f}')}° {'उ' if lat >= 0 else 'द'} / "
        f"{_to_dev(f'{abs(lon):.2f}')}° {'पू' if lon >= 0 else 'प'}"
    ) if lat is not None and lon is not None else "—"
    today = _to_dev(now.strftime(f"%-d {_MR_MONTHS_SHORT[now.month-1]} %Y"))

    tmpl = _jinja_env.get_template("mini_mr.html")
    html_str = tmpl.render(
        person_name=person_name or "—",
        place=place_name or "—",
        gender=gender or "—",
        gotra=gotra or "—",
        parents=parents or "—",
        birth_date_dev=birth_date_dev,
        birth_time_dev=birth_time_dev,
        latlon=latlon,
        tithi=tithi_mr, vara=vara_mr, yoga=yoga_mr, karana=karana_mr,
        moon_rashi=moon_rashi_mr,
        sun_rashi=sun_rashi_mr,
        lagna_rashi=lagna_rashi_mr,
        nakshatra=moon_nak_mr,
        charan=_to_dev(str(moon.nakshatra_pada)) if moon else "—",
        janmakshara=janmakshara,
        gana_yoni=f"{gana_mr} / {yoni_mr}",
        nadi_varna=f"{nadi_mr} / {varna_mr}",
        paya=paya_mr,
        sun_moon_rashi=f"{sun_rashi_mr} / {moon_rashi_mr}",
        rashi_swami_ratna=f"{rashi_swami_mr} / {ratna_mr}",
        maha_lord=maha_lord_mr, maha_range=maha_range,
        antar_lord=antar_lord_mr, antar_range=antar_range,
        d1_chart=d1_chart,
        today=today,
        astrologer_name=astrologer_name or "",
        astrologer_credentials=astrologer_credentials or "",
    )

    HTML = _weasyprint_html()
    return HTML(string=html_str, base_url=str(_PDF_TEMPLATE_DIR)).write_pdf(
        font_config=_get_font_config()
    )


