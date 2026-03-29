"""Phase 1 — Complete chart analysis & pre-computation.

Computes ALL data needed for predictions in one pass:
- Planet analysis (dignity, dispositor, nakshatra lord, navamsa, strength)
- House analysis (lord, occupants, aspects, arudha pada)
- 3-level Dasha tree (Maha → Antar → Pratyantar)
- All 16 Vargas with dignity per varga
- Shadbala + Vimshopaka (combined strength 0-10)
- Ashtakavarga (BAV/SAV)
- Yogas, Bhrigu Bindu, Arudha Lagna

Usage:
    chart = calculate_chart(birth)
    analysis = build_analysis(chart)
    # analysis.planets["Venus"].combined_strength → 7.2
    # analysis.get_dasha_at(datetime(2027,6,1)) → (Maha, Antar, Prat)
    # analysis.houses[7].lord_dignity → "Exalted"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from ..models import (
    BhriguBindu, Chart, PlanetPosition, ShadbalaResult,
    VargaChart, VimshopakaBala,
)
from .aspects import get_house_aspects
from .ashtakavarga import calculate_bav, calculate_sav
from .bhrigu import calculate_bhrigu_bindu
from .constants import AYANAMSHA, NAKSHATRA_LORDS, NAKSHATRAS, RASHIS
from .dasha import DASHA_SEQUENCE, DASHA_YEARS, TOTAL_DASHA_YEARS
from .shadbala import calculate_shadbala
from .strength import (
    DEBILITATION, ENEMIES, EXALTATION, FRIENDS, MOOLTRIKONA,
    NEUTRALS, OWN_SIGNS, RASHI_LORDS, get_dignity,
)
from .vargas import calculate_all_vargas, calculate_varga
from .vimshopaka import calculate_vimshopaka
from .yogas import detect_yogas


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PlanetAnalysis:
    """Complete analysis of a single planet."""
    name: str
    longitude: float
    rashi: str
    rashi_idx: int
    rashi_degree: float
    nakshatra: str
    nakshatra_pada: int
    nakshatra_lord: str          # Nakshatra dispositor
    house: int
    is_retrograde: bool
    speed: float
    dignity: str                 # D1 dignity
    dispositor: str              # Sign lord of planet's rashi
    dispositor_dignity: str      # Dignity of the dispositor
    navamsa_rashi: str           # D9 rashi
    navamsa_house: int           # D9 house from D9 lagna
    navamsa_dignity: str         # Dignity in D9
    shadbala: Optional[ShadbalaResult] = None
    vimshopaka: Optional[VimshopakaBala] = None
    combined_strength: float = 5.0   # 0-10 normalized
    strength_reasons: list[str] = field(default_factory=list)
    lordships: list[int] = field(default_factory=list)
    functional_nature: str = "neutral"
    is_combust: bool = False


@dataclass
class HouseAnalysis:
    """Complete analysis of a single house."""
    number: int
    rashi: str
    rashi_idx: int
    lord: str
    lord_planet: Optional[PlanetAnalysis] = None
    lord_house: int = 0          # Which house the lord sits in
    lord_dignity: str = ""
    occupants: list[str] = field(default_factory=list)
    aspecting_planets: list[str] = field(default_factory=list)
    arudha_rashi_idx: int = -1   # Arudha Pada of this house


@dataclass
class DashaPeriod:
    """Dasha period at any level."""
    lord: str
    start: datetime
    end: datetime
    level: int                   # 1=Maha, 2=Antar, 3=Pratyantar
    sub_periods: list[DashaPeriod] = field(default_factory=list)

    @property
    def duration_days(self) -> float:
        return (self.end - self.start).total_seconds() / 86400


@dataclass
class NakshatraChain:
    """Nakshatra dispositor chain for a planet.

    Planet → Nakshatra lord → that lord's nakshatra lord → ...
    The chain influences how a planet delivers results.
    """
    planet: str
    chain: list[str]       # [nak_lord, nak_lord_of_nak_lord, ...]
    chain_strength: float  # Average strength of chain (0-10)


@dataclass
class DispositorChain:
    """Sign dispositor chain for a planet.

    Planet → sign lord → that lord's sign lord → ...
    Terminates when a planet is in own sign or loop detected.
    """
    planet: str
    chain: list[str]        # [dispositor, dispositor's dispositor, ...]
    final_dispositor: str   # Planet where chain terminates
    chain_strong: bool      # Whether final dispositor is strong


@dataclass
class ChartAnalysis:
    """Complete pre-computed chart data — Phase 1 output.

    This is the single source of truth for all prediction engines.
    """
    chart: Chart
    planets: dict[str, PlanetAnalysis]
    houses: dict[int, HouseAnalysis]
    dashas: list[DashaPeriod]       # Top-level Maha dashas (with nested Antar/Prat)
    yogas: list[tuple[str, str]]
    bhrigu_bindu: BhriguBindu
    bav: dict[str, list[int]]
    sav: list[int]
    vargas: dict[int, VargaChart]
    lagna_rashi_idx: int
    moon_rashi_idx: int
    nakshatra_chains: dict[str, NakshatraChain] = field(default_factory=dict)
    dispositor_chains: dict[str, DispositorChain] = field(default_factory=dict)
    arudha_lagna_idx: int = -1

    # --- Query helpers ---

    def get_dasha_at(self, dt: datetime) -> tuple[
        Optional[DashaPeriod],
        Optional[DashaPeriod],
        Optional[DashaPeriod],
    ]:
        """Find Maha/Antar/Pratyantar dasha active at a given datetime."""
        maha = antar = prat = None
        for m in self.dashas:
            if m.start <= dt < m.end:
                maha = m
                for a in m.sub_periods:
                    if a.start <= dt < a.end:
                        antar = a
                        for p in a.sub_periods:
                            if p.start <= dt < p.end:
                                prat = p
                                break
                        break
                break
        return maha, antar, prat

    def house_lord(self, house: int) -> str:
        """Get the lord of a given house."""
        return self.houses[house].lord

    def planet_strength(self, name: str) -> float:
        """Get 0-10 combined strength of a planet."""
        pa = self.planets.get(name)
        return pa.combined_strength if pa else 5.0

    def is_planet_strong(self, name: str) -> bool:
        return self.planet_strength(name) >= 6.0

    def is_planet_weak(self, name: str) -> bool:
        return self.planet_strength(name) <= 3.5

    def get_occupants(self, house: int) -> list[str]:
        return self.houses[house].occupants

    def get_aspects_on(self, house: int) -> list[str]:
        return self.houses[house].aspecting_planets


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

_PLANET_NAMES = ["Sun", "Moon", "Mars", "Mercury", "Jupiter",
                 "Venus", "Saturn", "Rahu", "Ketu"]


def _functional_nature(houses: list[int]) -> str:
    """Determine functional nature from house lordship."""
    kendra = {1, 4, 7, 10}
    trikona = {1, 5, 9}
    trik = {6, 8, 12}
    h_set = set(houses)
    has_kendra = bool(h_set & kendra)
    has_trikona = bool(h_set & trikona)
    has_trik = bool(h_set & trik)

    if has_trikona and has_kendra:
        return "yogakaraka"
    if has_trikona and not has_trik:
        return "benefic"
    if has_trik and not has_trikona and not has_kendra:
        return "malefic"
    if has_kendra and not has_trikona and not has_trik:
        return "kendradhipati"
    if has_trikona and has_trik:
        return "mixed"
    return "neutral"


def _get_dignity_in_rashi(planet_name: str, rashi: str,
                          rashi_degree: float = 15.0) -> str:
    """Get dignity of a planet in any rashi (for varga charts)."""
    if planet_name in ("Rahu", "Ketu", "Lagna"):
        if planet_name in EXALTATION and EXALTATION[planet_name][0] == rashi:
            return "Exalted"
        if planet_name in DEBILITATION and DEBILITATION[planet_name][0] == rashi:
            return "Debilitated"
        return ""

    if planet_name in MOOLTRIKONA:
        mt_rashi, mt_start, mt_end = MOOLTRIKONA[planet_name]
        if rashi == mt_rashi and mt_start <= rashi_degree < mt_end:
            return "Mooltrikona"

    if planet_name in EXALTATION and EXALTATION[planet_name][0] == rashi:
        return "Exalted"
    if planet_name in DEBILITATION and DEBILITATION[planet_name][0] == rashi:
        return "Debilitated"
    if planet_name in OWN_SIGNS and rashi in OWN_SIGNS[planet_name]:
        return "Own Sign"

    rashi_lord = RASHI_LORDS.get(rashi, "")
    if rashi_lord == planet_name:
        return "Own Sign"
    if planet_name in FRIENDS and rashi_lord in FRIENDS[planet_name]:
        return "Friendly"
    if planet_name in ENEMIES and rashi_lord in ENEMIES[planet_name]:
        return "Enemy"
    return "Neutral"


def _is_combust(planet: PlanetPosition, sun: PlanetPosition) -> bool:
    """Check if a planet is combust (too close to Sun)."""
    if planet.name in ("Sun", "Rahu", "Ketu"):
        return False
    # Combustion orbs (degrees)
    orbs = {
        "Moon": 12, "Mars": 17, "Mercury": 14,
        "Jupiter": 11, "Venus": 10, "Saturn": 15,
    }
    orb = orbs.get(planet.name, 10)
    diff = abs(planet.longitude - sun.longitude)
    if diff > 180:
        diff = 360 - diff
    return diff <= orb


def _build_3level_dashas(chart: Chart) -> list[DashaPeriod]:
    """Build complete 3-level dasha tree: Maha → Antar → Pratyantar."""
    b = chart.birth_data
    birth_date = datetime(b.year, b.month, b.day, b.hour, b.minute, b.second)

    # Moon nakshatra
    moon = next(p for p in chart.planets if p.name == "Moon")
    nak_span = 360 / 27
    nak_idx = int(moon.longitude / nak_span) % 27
    fraction_elapsed = (moon.longitude % nak_span) / nak_span
    nak_lord = NAKSHATRA_LORDS[nak_idx]

    start_idx = DASHA_SEQUENCE.index(nak_lord)
    first_remaining = (1 - fraction_elapsed) * DASHA_YEARS[nak_lord] * 365.25

    mahas = []
    current = birth_date

    for i in range(18):  # Two full cycles to cover 120+ years
        lord = DASHA_SEQUENCE[(start_idx + i) % 9]
        if i == 0:
            maha_days = first_remaining
        else:
            maha_days = DASHA_YEARS[lord] * 365.25

        maha_end = current + timedelta(days=maha_days)
        maha_years = maha_days / 365.25

        # Antardashas
        antars = []
        ad_idx = DASHA_SEQUENCE.index(lord)
        ad_current = current

        for j in range(9):
            ad_lord = DASHA_SEQUENCE[(ad_idx + j) % 9]
            ad_days = (maha_years * DASHA_YEARS[ad_lord] / TOTAL_DASHA_YEARS) * 365.25
            ad_end = ad_current + timedelta(days=ad_days)
            ad_years = ad_days / 365.25

            # Pratyantardashas
            prats = []
            pd_idx = DASHA_SEQUENCE.index(ad_lord)
            pd_current = ad_current

            for k in range(9):
                pd_lord = DASHA_SEQUENCE[(pd_idx + k) % 9]
                pd_days = (ad_years * DASHA_YEARS[pd_lord] / TOTAL_DASHA_YEARS) * 365.25
                pd_end = pd_current + timedelta(days=pd_days)

                prats.append(DashaPeriod(
                    lord=pd_lord,
                    start=pd_current,
                    end=pd_end,
                    level=3,
                ))
                pd_current = pd_end

            antars.append(DashaPeriod(
                lord=ad_lord,
                start=ad_current,
                end=ad_end,
                level=2,
                sub_periods=prats,
            ))
            ad_current = ad_end

        mahas.append(DashaPeriod(
            lord=lord,
            start=current,
            end=maha_end,
            level=1,
            sub_periods=antars,
        ))
        current = maha_end

    return mahas


def _build_nakshatra_chain(planet_name: str,
                           all_planets: dict[str, PlanetPosition],
                           strengths: dict[str, float]) -> NakshatraChain:
    """Build nakshatra dispositor chain for a planet.

    Planet's nakshatra lord → that lord's nakshatra lord → ...
    Stops at 3 levels or when loop detected.
    """
    chain = []
    visited = {planet_name}
    current = planet_name

    for _ in range(3):
        p = all_planets.get(current)
        if not p:
            break
        nak_idx = int(p.longitude / (360 / 27)) % 27
        nak_lord = NAKSHATRA_LORDS[nak_idx]
        if nak_lord in visited:
            break
        chain.append(nak_lord)
        visited.add(nak_lord)
        current = nak_lord

    avg_str = 5.0
    if chain:
        avg_str = sum(strengths.get(p, 5.0) for p in chain) / len(chain)

    return NakshatraChain(
        planet=planet_name,
        chain=chain,
        chain_strength=round(avg_str, 1),
    )


def _build_dispositor_chain(planet_name: str,
                             all_planets: dict[str, PlanetPosition],
                             strengths: dict[str, float]) -> DispositorChain:
    """Build sign dispositor chain.

    Planet → sign lord → that lord's sign lord → ...
    Terminates when planet is in own sign or loop detected.
    """
    chain = []
    visited = {planet_name}
    current = planet_name

    for _ in range(7):
        p = all_planets.get(current)
        if not p:
            break
        disp = RASHI_LORDS.get(p.rashi, "")
        if not disp or disp in visited:
            break
        # Check if dispositor is in own sign (final dispositor)
        disp_planet = all_planets.get(disp)
        chain.append(disp)
        visited.add(disp)
        if disp_planet and disp_planet.rashi in OWN_SIGNS.get(disp, []):
            break
        current = disp

    final = chain[-1] if chain else planet_name
    return DispositorChain(
        planet=planet_name,
        chain=chain,
        final_dispositor=final,
        chain_strong=strengths.get(final, 5.0) >= 5.5,
    )


def _calculate_arudha(house: int, lord_house: int,
                       lagna_rashi_idx: int) -> int:
    """Calculate Arudha Pada for a house.

    Arudha = count from lord to house, then count same from lord forward.
    Exception: if arudha falls in same sign or 7th, use 10th from it.
    """
    # Lord's house position gives the rashi
    lord_rashi_idx = (lagna_rashi_idx + lord_house - 1) % 12
    house_rashi_idx = (lagna_rashi_idx + house - 1) % 12

    # Distance from house sign to lord sign
    dist = (lord_rashi_idx - house_rashi_idx) % 12

    # Arudha = dist counted from lord
    arudha_idx = (lord_rashi_idx + dist) % 12

    # BPHS exception: if arudha = house or 7th from house, take 10th from it
    if arudha_idx == house_rashi_idx:
        arudha_idx = (arudha_idx + 9) % 12  # 10th from it
    elif (arudha_idx - house_rashi_idx) % 12 == 6:
        arudha_idx = (arudha_idx + 9) % 12

    return arudha_idx


def _combined_strength(planet_name: str,
                       shadbala: dict, vimshopaka: dict,
                       dignity: str, navamsa_dignity: str,
                       is_retrograde: bool, is_combust: bool,
                       dispositor_strong: bool) -> tuple[float, list[str]]:
    """Compute comprehensive 0-10 strength score.

    Weighted:
      35% Shadbala
      25% Vimshopaka
      15% D1 dignity
      10% D9 dignity
       5% Combustion/Retrograde
       5% Dispositor health
       5% Nakshatra chain (applied externally)
    """
    reasons = []
    score = 0.0

    # 1. Shadbala (0-10)
    sb = shadbala.get(planet_name)
    if sb:
        sb_score = min(10, sb.ratio * 5)
        score += sb_score * 0.35
        if sb.ratio >= 1.5:
            reasons.append(f"Shadbala strong ({sb.total:.0f}/{sb.required:.0f})")
        elif sb.ratio < 0.8:
            reasons.append(f"Shadbala weak ({sb.total:.0f}/{sb.required:.0f})")
    else:
        score += 5.0 * 0.35

    # 2. Vimshopaka (0-10)
    vim = vimshopaka.get(planet_name)
    if vim:
        vim_score = vim.dasha_varga / 2  # 0-20 → 0-10
        score += vim_score * 0.25
        if vim.dasha_varga >= 15:
            reasons.append(f"Vargas strong (Vim:{vim.dasha_varga:.1f}/20)")
        elif vim.dasha_varga <= 8:
            reasons.append(f"Vargas weak (Vim:{vim.dasha_varga:.1f}/20)")
    else:
        score += 5.0 * 0.25

    # 3. D1 dignity (0-10)
    d1_map = {
        "Exalted": 10, "Mooltrikona": 8.5, "Own Sign": 8,
        "Friendly": 6, "Neutral": 5, "Enemy": 3, "Debilitated": 1,
    }
    d1_score = d1_map.get(dignity, 5)
    score += d1_score * 0.15
    if d1_score >= 8:
        reasons.append(f"D1 {dignity}")
    elif d1_score <= 3:
        reasons.append(f"D1 {dignity}")

    # 4. D9 dignity (0-10)
    d9_score = d1_map.get(navamsa_dignity, 5)
    score += d9_score * 0.10
    if d9_score >= 8:
        reasons.append(f"D9 {navamsa_dignity}")
    elif d9_score <= 3:
        reasons.append(f"D9 {navamsa_dignity}")

    # 5. Retrograde/Combust (-/+)
    retro_score = 5.0
    if is_combust:
        retro_score = 2.0
        reasons.append("Combust")
    elif is_retrograde and planet_name not in ("Rahu", "Ketu"):
        # Retrograde planets have complex effects: strong in strength but
        # can give reversed or delayed results
        retro_score = 6.0  # Slightly above neutral (strong but karmic)
        reasons.append("Retrograde (strong but delayed)")
    score += retro_score * 0.05

    # 6. Dispositor health
    disp_score = 7.0 if dispositor_strong else 3.5
    score += disp_score * 0.05

    # 7. Reserve 5% for nakshatra chain (applied in build_analysis)

    return round(max(0, min(10, score / 0.95)), 1), reasons


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_analysis(chart: Chart) -> ChartAnalysis:
    """Build complete ChartAnalysis from a natal chart.

    This is the Phase 1 entry point. Call once, then pass the result
    to any prediction engine.
    """
    lagna_rashi_idx = int(chart.lagna.longitude / 30) % 12
    moon = next(p for p in chart.planets if p.name == "Moon")
    moon_rashi_idx = int(moon.longitude / 30) % 12
    sun = next(p for p in chart.planets if p.name == "Sun")
    all_planets_pos = {p.name: p for p in chart.planets}

    # === Pre-compute core systems ===
    bav = calculate_bav(chart)
    sav = calculate_sav(bav)
    vargas = calculate_all_vargas(chart)
    vimshopaka = calculate_vimshopaka(chart, vargas)
    shadbala = calculate_shadbala(chart, vimshopaka)
    house_aspects = get_house_aspects(chart)
    yogas = detect_yogas(chart)
    bb = calculate_bhrigu_bindu(chart)

    # Navamsa (D9) for quick lookup
    d9 = vargas.get(9)
    d9_positions = {}
    if d9:
        for pos in d9.positions:
            d9_positions[pos.name] = pos

    # === House lordships ===
    house_lord_map = {}
    planet_lordships: dict[str, list[int]] = {}
    for h in range(1, 13):
        rashi = RASHIS[(lagna_rashi_idx + h - 1) % 12]
        lord = RASHI_LORDS[rashi]
        house_lord_map[h] = lord
        planet_lordships.setdefault(lord, []).append(h)

    # === Build Planet Analysis ===
    planet_analyses: dict[str, PlanetAnalysis] = {}

    # First pass: basic data (need all before dispositor chains)
    for p in chart.planets:
        if p.name == "Lagna":
            continue

        nak_idx = int(p.longitude / (360 / 27)) % 27
        nak_lord = NAKSHATRA_LORDS[nak_idx]
        dispositor = RASHI_LORDS.get(p.rashi, p.name)
        dignity = get_dignity(p)
        combust = _is_combust(p, sun)

        # D9 data
        d9_pos = d9_positions.get(p.name)
        nav_rashi = d9_pos.rashi if d9_pos else ""
        nav_house = d9_pos.house if d9_pos else 0
        nav_dignity = _get_dignity_in_rashi(p.name, nav_rashi) if nav_rashi else ""

        # Dispositor dignity
        disp_planet = all_planets_pos.get(dispositor)
        disp_dignity = get_dignity(disp_planet) if disp_planet else ""

        lordships = planet_lordships.get(p.name, [])
        func_nature = _functional_nature(lordships) if lordships else "neutral"

        pa = PlanetAnalysis(
            name=p.name,
            longitude=p.longitude,
            rashi=p.rashi,
            rashi_idx=int(p.longitude / 30) % 12,
            rashi_degree=p.rashi_degree,
            nakshatra=p.nakshatra,
            nakshatra_pada=p.nakshatra_pada,
            nakshatra_lord=nak_lord,
            house=p.house,
            is_retrograde=p.is_retrograde,
            speed=p.speed,
            dignity=dignity,
            dispositor=dispositor,
            dispositor_dignity=disp_dignity,
            navamsa_rashi=nav_rashi,
            navamsa_house=nav_house,
            navamsa_dignity=nav_dignity,
            shadbala=shadbala.get(p.name),
            vimshopaka=vimshopaka.get(p.name),
            lordships=lordships,
            functional_nature=func_nature,
            is_combust=combust,
        )
        planet_analyses[p.name] = pa

    # Second pass: combined strength + chains (needs all planets)
    # Temporary strength map for chain calculations
    temp_strengths: dict[str, float] = {}
    for name, pa in planet_analyses.items():
        disp_pa = planet_analyses.get(pa.dispositor)
        disp_strong = False
        if disp_pa:
            disp_strong = disp_pa.dignity in ("Exalted", "Mooltrikona", "Own Sign", "Friendly")

        strength, reasons = _combined_strength(
            name, shadbala, vimshopaka,
            pa.dignity, pa.navamsa_dignity,
            pa.is_retrograde, pa.is_combust,
            disp_strong,
        )
        pa.combined_strength = strength
        pa.strength_reasons = reasons
        temp_strengths[name] = strength

    # Nakshatra chains
    nak_chains = {}
    for name in _PLANET_NAMES:
        if name in all_planets_pos:
            nc = _build_nakshatra_chain(name, all_planets_pos, temp_strengths)
            nak_chains[name] = nc
            # Apply 5% nakshatra chain influence
            if name in planet_analyses:
                pa = planet_analyses[name]
                chain_adj = (nc.chain_strength - 5.0) * 0.05
                pa.combined_strength = round(
                    max(0, min(10, pa.combined_strength + chain_adj)), 1)

    # Dispositor chains
    disp_chains = {}
    for name in _PLANET_NAMES:
        if name in all_planets_pos:
            disp_chains[name] = _build_dispositor_chain(
                name, all_planets_pos, temp_strengths)

    # === Build House Analysis ===
    house_analyses: dict[int, HouseAnalysis] = {}
    for h in range(1, 13):
        rashi_idx = (lagna_rashi_idx + h - 1) % 12
        rashi = RASHIS[rashi_idx]
        lord = house_lord_map[h]
        lord_pa = planet_analyses.get(lord)

        occupants = [p.name for p in chart.planets
                     if p.house == h and p.name != "Lagna"]

        # Arudha Pada
        lord_house = lord_pa.house if lord_pa else h
        arudha_idx = _calculate_arudha(h, lord_house, lagna_rashi_idx)

        house_analyses[h] = HouseAnalysis(
            number=h,
            rashi=rashi,
            rashi_idx=rashi_idx,
            lord=lord,
            lord_planet=lord_pa,
            lord_house=lord_house,
            lord_dignity=lord_pa.dignity if lord_pa else "",
            occupants=occupants,
            aspecting_planets=house_aspects.get(h, []),
            arudha_rashi_idx=arudha_idx,
        )

    # Arudha Lagna = Arudha Pada of 1st house
    arudha_lagna_idx = house_analyses[1].arudha_rashi_idx

    # === 3-level Dasha tree ===
    dashas = _build_3level_dashas(chart)

    return ChartAnalysis(
        chart=chart,
        planets=planet_analyses,
        houses=house_analyses,
        dashas=dashas,
        yogas=yogas,
        bhrigu_bindu=bb,
        bav=bav,
        sav=sav,
        vargas=vargas,
        lagna_rashi_idx=lagna_rashi_idx,
        moon_rashi_idx=moon_rashi_idx,
        nakshatra_chains=nak_chains,
        dispositor_chains=disp_chains,
        arudha_lagna_idx=arudha_lagna_idx,
    )
