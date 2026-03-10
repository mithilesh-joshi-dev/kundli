from dataclasses import dataclass, field


@dataclass
class BirthData:
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    latitude: float
    longitude: float
    utc_offset: float  # hours, e.g. +5.5 for IST


@dataclass
class PlanetPosition:
    name: str
    longitude: float
    rashi: str
    rashi_degree: float
    nakshatra: str
    nakshatra_pada: int
    house: int
    is_retrograde: bool
    speed: float = 0.0  # degrees/day, negative = retrograde


@dataclass
class Chart:
    birth_data: BirthData
    ayanamsha_value: float
    lagna: PlanetPosition
    planets: list[PlanetPosition]


# --- Divisional chart models ---

@dataclass
class VargaPosition:
    """A planet's position in a divisional chart."""
    name: str
    rashi_idx: int     # 0-11
    rashi: str
    house: int         # 1-12 relative to varga lagna


@dataclass
class VargaChart:
    """Complete divisional chart."""
    division: int      # D-number (1, 2, 3, ... 60)
    label: str         # "Hora", "Drekkana", etc.
    lagna_rashi_idx: int
    positions: list[VargaPosition] = field(default_factory=list)


# --- Strength models ---

@dataclass
class ShadbalaResult:
    """Six-fold strength for a planet."""
    planet: str
    sthana_bala: float   # positional
    dig_bala: float      # directional
    kala_bala: float     # temporal
    cheshta_bala: float  # motional
    naisargika_bala: float  # natural
    drig_bala: float     # aspectual
    total: float = 0.0
    required: float = 0.0
    ratio: float = 0.0

    def __post_init__(self):
        self.total = (self.sthana_bala + self.dig_bala + self.kala_bala +
                      self.cheshta_bala + self.naisargika_bala + self.drig_bala)
        if self.required > 0:
            self.ratio = self.total / self.required


@dataclass
class VimshopakaBala:
    """Vimshopaka strength across varga groups (max 20 each)."""
    planet: str
    shad_varga: float = 0.0       # 6-chart
    sapta_varga: float = 0.0      # 7-chart
    dasha_varga: float = 0.0      # 10-chart
    shodasha_varga: float = 0.0   # 16-chart


@dataclass
class BhriguBindu:
    """Bhrigu Bindu — Rahu-Moon midpoint."""
    longitude: float
    rashi: str
    rashi_degree: float
    house: int  # from lagna
