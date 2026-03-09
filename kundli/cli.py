from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .calc.engine import calculate_chart
from .calc.geocode import fuzzy_search, lookup_city
from .calc.transit import calculate_transits
from .display.terminal import print_chart, print_matching
from .models import BirthData

app = typer.Typer(help="Kundli - Vedic Astrology Birth Chart Generator")
console = Console()


def _parse_birth(date: str, time: str, lat: float | None, lon: float | None,
                 place: str | None, utc_offset: float) -> BirthData:
    # Parse place
    if place:
        result = lookup_city(place)
        if result:
            lat, lon, utc_offset = result
        else:
            matches = fuzzy_search(place)
            if matches:
                console.print(f"[yellow]City '{place}' not found exactly. Did you mean:[/yellow]")
                for name, lt, ln in matches:
                    console.print(f"  {name} ({lt:.4f}°N, {ln:.4f}°E)")
                raise typer.Exit(1)
            else:
                console.print(f"[red]City '{place}' not found. Use --lat and --lon instead.[/red]")
                raise typer.Exit(1)

    if lat is None or lon is None:
        console.print("[red]Error: provide --place or both --lat and --lon[/red]")
        raise typer.Exit(1)

    # Parse date
    parts = date.split("-")
    if len(parts) != 3:
        console.print("[red]Error: date must be YYYY-MM-DD[/red]")
        raise typer.Exit(1)
    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])

    # Parse time
    tparts = time.split(":")
    if len(tparts) < 2:
        console.print("[red]Error: time must be HH:MM or HH:MM:SS[/red]")
        raise typer.Exit(1)
    hour, minute = int(tparts[0]), int(tparts[1])
    second = int(tparts[2]) if len(tparts) > 2 else 0

    return BirthData(
        year=year, month=month, day=day,
        hour=hour, minute=minute, second=second,
        latitude=lat, longitude=lon,
        utc_offset=utc_offset,
    )


@app.command("chart")
def chart(
    date: str = typer.Option(..., help="Birth date (YYYY-MM-DD)"),
    time: str = typer.Option(..., help="Birth time (HH:MM or HH:MM:SS)"),
    place: Optional[str] = typer.Option(None, help="City name (e.g., 'Pune', 'Delhi')"),
    lat: Optional[float] = typer.Option(None, help="Birth place latitude"),
    lon: Optional[float] = typer.Option(None, help="Birth place longitude"),
    utc_offset: float = typer.Option(5.5, "--utc", help="UTC offset in hours (default: +5.5 IST)"),
):
    """Generate a Vedic birth chart (full report)."""
    birth = _parse_birth(date, time, lat, lon, place, utc_offset)
    result = calculate_chart(birth)
    print_chart(result)


@app.command("transit")
def transit(
    date: str = typer.Option(..., help="Birth date (YYYY-MM-DD)"),
    time: str = typer.Option(..., help="Birth time (HH:MM or HH:MM:SS)"),
    place: Optional[str] = typer.Option(None, help="City name"),
    lat: Optional[float] = typer.Option(None, help="Birth place latitude"),
    lon: Optional[float] = typer.Option(None, help="Birth place longitude"),
    utc_offset: float = typer.Option(5.5, "--utc", help="UTC offset in hours"),
    start: int = typer.Option(2025, "--from", help="Start year"),
    end: int = typer.Option(2027, "--to", help="End year"),
    planets: Optional[str] = typer.Option(None, "--planets", help="Comma-separated planets (default: Jupiter,Saturn,Rahu,Ketu,Mars)"),
):
    """Show planetary transits (Gochar) for a birth chart."""
    birth = _parse_birth(date, time, lat, lon, place, utc_offset)
    result = calculate_chart(birth)

    lagna_rashi_idx = int(result.lagna.longitude / 30) % 12
    moon = next(p for p in result.planets if p.name == "Moon")
    moon_rashi_idx = int(moon.longitude / 30) % 12

    planet_list = None
    if planets:
        planet_list = [p.strip().title() for p in planets.split(",")]

    console.print()
    console.print(f"[bold]Transit (Gochar) Report[/bold]")
    console.print(f"Lagna: {result.lagna.rashi}  |  Moon: {moon.rashi}")
    console.print(f"Period: {start} to {end}")

    transits = calculate_transits(lagna_rashi_idx, moon_rashi_idx, start, end, planet_list)

    for planet_name, entries in transits.items():
        console.print()
        table = Table(title=f"{planet_name} Transit", show_lines=False)
        table.add_column("From", min_width=12)
        table.add_column("To", min_width=12)
        table.add_column("Rashi", min_width=12)
        table.add_column("From Lagna", justify="center")
        table.add_column("From Moon", justify="center")

        for start_date, rashi, h_lagna, h_moon, end_date in entries:
            table.add_row(
                start_date,
                end_date or "...",
                rashi,
                f"H{h_lagna}",
                f"H{h_moon}",
            )

        console.print(table)


@app.command("match")
def match(
    bride_date: str = typer.Option(..., "--bride-date", help="Bride birth date (YYYY-MM-DD)"),
    bride_time: str = typer.Option(..., "--bride-time", help="Bride birth time (HH:MM or HH:MM:SS)"),
    bride_place: Optional[str] = typer.Option(None, "--bride-place", help="Bride city name"),
    bride_lat: Optional[float] = typer.Option(None, "--bride-lat", help="Bride latitude"),
    bride_lon: Optional[float] = typer.Option(None, "--bride-lon", help="Bride longitude"),
    groom_date: str = typer.Option(..., "--groom-date", help="Groom birth date (YYYY-MM-DD)"),
    groom_time: str = typer.Option(..., "--groom-time", help="Groom birth time (HH:MM or HH:MM:SS)"),
    groom_place: Optional[str] = typer.Option(None, "--groom-place", help="Groom city name"),
    groom_lat: Optional[float] = typer.Option(None, "--groom-lat", help="Groom latitude"),
    groom_lon: Optional[float] = typer.Option(None, "--groom-lon", help="Groom longitude"),
    utc_offset: float = typer.Option(5.5, "--utc", help="UTC offset in hours"),
):
    """Ashtakoot Milan — marriage compatibility matching."""
    bride_birth = _parse_birth(bride_date, bride_time, bride_lat, bride_lon, bride_place, utc_offset)
    groom_birth = _parse_birth(groom_date, groom_time, groom_lat, groom_lon, groom_place, utc_offset)

    bride_chart = calculate_chart(bride_birth)
    groom_chart = calculate_chart(groom_birth)

    print_matching(bride_chart, groom_chart)


@app.command("search")
def search_city(
    name: str = typer.Argument(help="City name to search"),
):
    """Search for a city's coordinates."""
    exact = lookup_city(name)
    if exact:
        lat, lon, utc = exact
        console.print(f"[bold]{name.title()}[/bold]: {lat:.4f}°N, {lon:.4f}°E (UTC+{utc})")
        return

    matches = fuzzy_search(name)
    if matches:
        console.print(f"[bold]Matches for '{name}':[/bold]")
        for city, lat, lon in matches:
            console.print(f"  {city}: {lat:.4f}°N, {lon:.4f}°E")
    else:
        console.print(f"[yellow]No matches for '{name}'. Use --lat and --lon instead.[/yellow]")


if __name__ == "__main__":
    app()
