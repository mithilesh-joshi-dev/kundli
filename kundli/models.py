from dataclasses import dataclass


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


@dataclass
class Chart:
    birth_data: BirthData
    ayanamsha_value: float
    lagna: PlanetPosition
    planets: list[PlanetPosition]
