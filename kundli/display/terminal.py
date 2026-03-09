from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text

from ..calc.aspects import get_aspects, get_house_aspects
from ..calc.constants import RASHIS, RASHI_ELEMENTS, RASHI_QUALITIES, NAKSHATRA_LORDS, NAKSHATRAS
from ..calc.dasha import calculate_dasha
from ..calc.matching import calculate_matching
from ..calc.nakshatra_attrs import get_nakshatra_attrs
from ..calc.navamsa import calculate_navamsa
from ..calc.panchang import calculate_panchang
from ..calc.strength import RASHI_LORDS, get_dignity
from ..calc.utils import dms_str, longitude_to_nakshatra
from ..calc.yogas import detect_yogas
from ..models import Chart

console = Console()


def print_chart(chart: Chart, full: bool = True) -> None:
    b = chart.birth_data
    utc_sign = "+" if b.utc_offset >= 0 else ""

    # === Birth Details ===
    console.print()
    console.print(Panel.fit(
        f"[bold]Vedic Birth Chart (Kundli)[/bold]\n"
        f"Date: {b.year}-{b.month:02d}-{b.day:02d}  "
        f"Time: {b.hour:02d}:{b.minute:02d}:{b.second:02d}  "
        f"UTC{utc_sign}{b.utc_offset}\n"
        f"Location: {b.latitude:.4f}°N, {b.longitude:.4f}°E\n"
        f"Ayanamsha (Lahiri): {chart.ayanamsha_value:.4f}°",
        title="Birth Details",
    ))

    # === Panchang ===
    panchang = calculate_panchang(
        b.year, b.month, b.day, b.hour, b.minute, b.second, b.utc_offset)
    _print_panchang(chart, panchang)

    # === Lagna Details ===
    _print_lagna_details(chart)

    # === Planet Positions ===
    _print_planet_table(chart)

    # === House Summary ===
    _print_house_summary(chart)

    if full:
        # === Navamsa (D9) ===
        _print_navamsa(chart)

        # === Planetary Dignity ===
        _print_dignity_summary(chart)

        # === Aspects ===
        _print_aspects(chart)

        # === Yogas ===
        _print_yogas(chart)

        # === Vimshottari Dasha ===
        _print_dasha(chart)


def _print_panchang(chart: Chart, panchang: dict) -> None:
    console.print()
    moon = next(p for p in chart.planets if p.name == "Moon")
    _, moon_nak, moon_pada = longitude_to_nakshatra(moon.longitude)
    nak_idx = NAKSHATRAS.index(moon_nak)
    nak_lord = NAKSHATRA_LORDS[nak_idx]

    attrs = get_nakshatra_attrs(nak_idx)
    lines = [
        f"[bold]Vara (Day):[/bold] {panchang['vara']}    [bold]Tithi:[/bold] {panchang['tithi']}",
        f"[bold]Yoga:[/bold] {panchang['yoga']}    [bold]Karana:[/bold] {panchang['karana']}",
        f"[bold]Birth Star:[/bold] {moon_nak} (Pada {moon_pada})    [bold]Nakshatra Lord:[/bold] {nak_lord}",
        f"[bold]Moon Rashi:[/bold] {moon.rashi}    [bold]Rashi Lord:[/bold] {RASHI_LORDS[moon.rashi]}",
        f"[bold]Gana:[/bold] {attrs['gana']}    [bold]Yoni:[/bold] {attrs['yoni']} ({attrs['yoni_gender']})"
        f"    [bold]Nadi:[/bold] {attrs['nadi']}    [bold]Varna:[/bold] {attrs['varna']}",
    ]
    console.print(Panel("\n".join(lines), title="Panchang & Birth Star"))


def _print_lagna_details(chart: Chart) -> None:
    console.print()
    lagna = chart.lagna
    lagna_rashi = lagna.rashi
    lagna_lord = RASHI_LORDS[lagna_rashi]
    element = RASHI_ELEMENTS[lagna_rashi]
    quality = RASHI_QUALITIES[lagna_rashi]

    # Find lagna lord's position
    lagna_lord_pos = next((p for p in chart.planets if p.name == lagna_lord), None)
    lord_info = ""
    if lagna_lord_pos:
        lord_info = (f"{lagna_lord} in {lagna_lord_pos.rashi} "
                     f"(House {lagna_lord_pos.house})")

    console.print(Panel.fit(
        f"[bold green]Lagna:[/bold green] {lagna_rashi} {dms_str(lagna.rashi_degree)}\n"
        f"[bold]Nakshatra:[/bold] {lagna.nakshatra} Pada {lagna.nakshatra_pada}\n"
        f"[bold]Lagna Lord:[/bold] {lord_info}\n"
        f"[bold]Element:[/bold] {element}  |  [bold]Quality:[/bold] {quality}",
        title="Lagna (Ascendant)",
    ))


def _print_planet_table(chart: Chart) -> None:
    console.print()
    table = Table(title="Planet Positions (Graha Sthiti)", show_lines=True)
    table.add_column("Planet", style="bold cyan", min_width=8)
    table.add_column("Rashi", min_width=10)
    table.add_column("Degree", min_width=10)
    table.add_column("Longitude", min_width=10)
    table.add_column("Nakshatra", min_width=16)
    table.add_column("Pada", justify="center")
    table.add_column("Nak Lord", min_width=8)
    table.add_column("House", justify="center")
    table.add_column("R", justify="center")
    table.add_column("Dignity", min_width=12)

    for p in chart.planets:
        retro = "R" if p.is_retrograde else ""
        dignity = get_dignity(p)
        dignity_style = _dignity_color(dignity)
        nak_idx = NAKSHATRAS.index(p.nakshatra)
        nak_lord = NAKSHATRA_LORDS[nak_idx]
        table.add_row(
            p.name, p.rashi,
            dms_str(p.rashi_degree), dms_str(p.longitude),
            p.nakshatra, str(p.nakshatra_pada), nak_lord,
            str(p.house), retro,
            f"[{dignity_style}]{dignity}[/{dignity_style}]" if dignity else "",
        )

    console.print(table)


def _dignity_color(dignity: str) -> str:
    return {
        "Exalted": "bold green",
        "Mooltrikona": "green",
        "Own Sign": "cyan",
        "Friendly": "blue",
        "Neutral": "yellow",
        "Enemy": "red",
        "Debilitated": "bold red",
    }.get(dignity, "white")


def _print_house_summary(chart: Chart) -> None:
    console.print()
    lagna_rashi_idx = int(chart.lagna.longitude / 30) % 12

    table = Table(title="Bhava Chart (House Summary — Whole Sign)", show_lines=False)
    table.add_column("House", justify="center", style="bold")
    table.add_column("Rashi", min_width=10)
    table.add_column("Lord", min_width=8)
    table.add_column("Planets", min_width=30)
    table.add_column("Aspected By", min_width=25)

    houses: dict[int, list[str]] = {i: [] for i in range(1, 13)}
    for p in chart.planets:
        houses[p.house].append(p.name)

    house_asp = get_house_aspects(chart)

    for h in range(1, 13):
        rashi = RASHIS[(lagna_rashi_idx + h - 1) % 12]
        lord = RASHI_LORDS[rashi]
        occupants = ", ".join(houses[h]) if houses[h] else "—"
        aspects = ", ".join(house_asp[h]) if house_asp[h] else "—"
        table.add_row(str(h), rashi, lord, occupants, aspects)

    console.print(table)


def _print_navamsa(chart: Chart) -> None:
    console.print()
    navamsa = calculate_navamsa(chart)

    table = Table(title="Navamsa Chart (D9)", show_lines=True)
    table.add_column("Planet", style="bold cyan", min_width=10)
    table.add_column("Navamsa Rashi", min_width=12)
    table.add_column("Navamsa House", justify="center")

    for name, rashi, house in navamsa:
        style = "bold green" if name == "Lagna" else ""
        table.add_row(f"[{style}]{name}[/{style}]" if style else name,
                      rashi, str(house))

    # Navamsa house summary
    nav_lagna_rashi = navamsa[0][1]
    nav_houses: dict[int, list[str]] = {i: [] for i in range(1, 13)}
    for name, rashi, house in navamsa[1:]:  # skip lagna
        nav_houses[house].append(name)

    console.print(table)

    console.print()
    nav_lagna_idx = RASHIS.index(nav_lagna_rashi)
    console.print(f"[bold]Navamsa Lagna:[/bold] {nav_lagna_rashi} ({RASHI_LORDS[nav_lagna_rashi]})")

    # Vargottama check (planet in same rashi in both Rashi and Navamsa)
    vargottama = []
    for name, nav_rashi, _ in navamsa[1:]:
        planet = next((p for p in chart.planets if p.name == name), None)
        if planet and planet.rashi == nav_rashi:
            vargottama.append(name)
    if vargottama:
        console.print(f"[bold yellow]Vargottama Planets:[/bold yellow] {', '.join(vargottama)} "
                      f"(same rashi in Rashi & Navamsa — extra strength)")


def _print_dignity_summary(chart: Chart) -> None:
    console.print()
    table = Table(title="Planetary Dignity & Strength", show_lines=False)
    table.add_column("Planet", style="bold cyan", min_width=8)
    table.add_column("Rashi", min_width=10)
    table.add_column("Rashi Lord", min_width=10)
    table.add_column("Dignity", min_width=12)
    table.add_column("Retrograde", justify="center")

    for p in chart.planets:
        dignity = get_dignity(p)
        color = _dignity_color(dignity) if dignity else "white"
        table.add_row(
            p.name, p.rashi, RASHI_LORDS[p.rashi],
            f"[{color}]{dignity}[/{color}]" if dignity else "—",
            "Yes" if p.is_retrograde else "—",
        )

    console.print(table)


def _print_aspects(chart: Chart) -> None:
    console.print()
    aspects = get_aspects(chart)

    table = Table(title="Planetary Aspects (Graha Drishti)", show_lines=False)
    table.add_column("Planet", style="bold cyan", min_width=8)
    table.add_column("Aspects", min_width=8)
    table.add_column("Type", min_width=15)

    for src, tgt, dist in aspects:
        ordinal = {3: "3rd", 4: "4th", 5: "5th", 7: "7th", 8: "8th", 9: "9th", 10: "10th"}.get(dist, f"{dist}th")
        if dist == 7:
            aspect_type = f"7th (full)"
        elif dist in (4, 8) and src == "Mars":
            aspect_type = f"Mars special ({ordinal})"
        elif dist in (5, 9) and src in ("Jupiter", "Rahu", "Ketu"):
            aspect_type = f"{src} special ({ordinal})"
        elif dist in (3, 10) and src == "Saturn":
            aspect_type = f"Saturn special ({ordinal})"
        else:
            aspect_type = f"Special ({ordinal})"
        table.add_row(src, tgt, aspect_type)

    console.print(table)


def _print_yogas(chart: Chart) -> None:
    console.print()
    yogas = detect_yogas(chart)

    if not yogas:
        console.print("[bold]Yogas:[/bold] None detected")
        return

    console.print(Panel.fit(
        "\n".join(f"[bold yellow]{name}[/bold yellow]: {desc}" for name, desc in yogas),
        title="Yogas & Doshas",
    ))


def _print_dasha(chart: Chart) -> None:
    console.print()
    dashas = calculate_dasha(chart)
    now = datetime.now()

    # Mahadasha table
    table = Table(title="Vimshottari Mahadasha", show_lines=True)
    table.add_column("Mahadasha", style="bold cyan", min_width=10)
    table.add_column("Start", min_width=12)
    table.add_column("End", min_width=12)
    table.add_column("Duration", justify="center")
    table.add_column("Active", justify="center")

    current_maha = None
    for lord, start, end, antardashas in dashas:
        is_active = start <= now < end
        active_marker = "[bold green]◄ Current[/bold green]" if is_active else ""
        years = (end - start).days / 365.25
        table.add_row(
            lord,
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
            f"{years:.1f}y",
            active_marker,
        )
        if is_active:
            current_maha = (lord, start, end, antardashas)

    console.print(table)

    # Antardasha for current Mahadasha
    if current_maha:
        lord, _, _, antardashas = current_maha
        console.print()
        ad_table = Table(title=f"Antardasha in {lord} Mahadasha", show_lines=False)
        ad_table.add_column("Antardasha", style="bold", min_width=10)
        ad_table.add_column("Start", min_width=12)
        ad_table.add_column("End", min_width=12)
        ad_table.add_column("Duration", justify="center")
        ad_table.add_column("Active", justify="center")

        for ad_lord, ad_start, ad_end in antardashas:
            is_ad_active = ad_start <= now < ad_end
            marker = "[bold green]◄ Current[/bold green]" if is_ad_active else ""
            ad_months = (ad_end - ad_start).days / 30.44
            ad_table.add_row(
                ad_lord,
                ad_start.strftime("%Y-%m-%d"),
                ad_end.strftime("%Y-%m-%d"),
                f"{ad_months:.0f}m",
                marker,
            )

        console.print(ad_table)

    # Full antardasha for ALL mahadashas
    console.print()
    for lord, start, end, antardashas in dashas:
        if current_maha and lord == current_maha[0]:
            continue  # Already printed above
        console.print(f"[dim]  {lord} ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}): "
                      f"{', '.join(f'{al}' for al, _, _ in antardashas)}[/dim]")


def print_matching(bride_chart: Chart, groom_chart: Chart) -> None:
    """Print Ashtakoot Milan (marriage compatibility) report."""
    results = calculate_matching(bride_chart, groom_chart)

    # Bride and Groom info
    b_moon = next(p for p in bride_chart.planets if p.name == "Moon")
    g_moon = next(p for p in groom_chart.planets if p.name == "Moon")
    b_nak_idx = NAKSHATRAS.index(b_moon.nakshatra)
    g_nak_idx = NAKSHATRAS.index(g_moon.nakshatra)
    b_attrs = get_nakshatra_attrs(b_nak_idx)
    g_attrs = get_nakshatra_attrs(g_nak_idx)

    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Bride:[/bold cyan]  Moon in {b_moon.rashi} | {b_moon.nakshatra} Pada {b_moon.nakshatra_pada}"
        f" | Gana: {b_attrs['gana']} | Yoni: {b_attrs['yoni']} | Nadi: {b_attrs['nadi']}\n"
        f"[bold cyan]Groom:[/bold cyan]  Moon in {g_moon.rashi} | {g_moon.nakshatra} Pada {g_moon.nakshatra_pada}"
        f" | Gana: {g_attrs['gana']} | Yoni: {g_attrs['yoni']} | Nadi: {g_attrs['nadi']}",
        title="Ashtakoot Milan (Kundli Matching)",
    ))
    console.print()

    table = Table(title="Compatibility Scores", show_lines=True)
    table.add_column("Koota", style="bold", min_width=14)
    table.add_column("Score", justify="center", min_width=8)
    table.add_column("Max", justify="center", min_width=5)
    table.add_column("Details", min_width=40)

    total = 0.0
    max_total = 0.0

    for koota, score, max_score, desc in results:
        total += score
        max_total += max_score
        if score == max_score:
            style = "green"
        elif score >= max_score / 2:
            style = "yellow"
        else:
            style = "red"
        table.add_row(
            koota,
            f"[{style}]{score:.1f}[/{style}]",
            f"{max_score:.0f}",
            desc,
        )

    # Total row
    pct = (total / max_total) * 100
    if pct >= 60:
        total_style = "bold green"
    elif pct >= 40:
        total_style = "bold yellow"
    else:
        total_style = "bold red"

    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[{total_style}]{total:.1f}[/{total_style}]",
        f"{max_total:.0f}",
        f"[{total_style}]{pct:.0f}%[/{total_style}]",
    )

    console.print(table)

    # Verdict
    console.print()
    if pct >= 60:
        verdict = "[bold green]Excellent match! (≥18/36) — Marriage is recommended.[/bold green]"
    elif pct >= 50:
        verdict = "[bold yellow]Good match (18-21/36) — Marriage is acceptable with some adjustments.[/bold yellow]"
    elif pct >= 40:
        verdict = "[bold yellow]Average match — Consider carefully, remedies may be needed.[/bold yellow]"
    else:
        verdict = "[bold red]Below average match — Marriage is not recommended without significant remedies.[/bold red]"
    console.print(Panel.fit(verdict, title="Verdict"))
