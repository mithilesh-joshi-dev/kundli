"""All 16 Parashari divisional charts (Shodasha Varga).

Each Dn divides the 30° rashi into n parts and maps each part
to a rashi based on classical rules from BPHS Ch. 6-7.
"""

from ..models import Chart, VargaChart, VargaPosition
from .constants import RASHIS, RASHI_QUALITIES, VARGA_LABELS


def _rashi_idx(lon: float) -> int:
    return int(lon / 30) % 12


def _deg_in_rashi(lon: float) -> float:
    return lon % 30


def _is_odd_rashi(rashi_idx: int) -> bool:
    return rashi_idx % 2 == 0  # Mesha=0 is odd


# ===== Individual varga rashi calculators =====
# Each takes sidereal longitude, returns varga rashi index (0-11)

def _d1(lon: float) -> int:
    """D1 Rashi — natal chart."""
    return _rashi_idx(lon)


def _d2(lon: float) -> int:
    """D2 Hora — Sun/Moon wealth chart.

    Odd rashi: 0-15° = Simha (Sun), 15-30° = Karka (Moon).
    Even rashi: 0-15° = Karka (Moon), 15-30° = Simha (Sun).
    """
    ri = _rashi_idx(lon)
    deg = _deg_in_rashi(lon)
    odd = _is_odd_rashi(ri)
    if odd:
        return 4 if deg < 15 else 3  # Simha=4, Karka=3
    else:
        return 3 if deg < 15 else 4


def _d3(lon: float) -> int:
    """D3 Drekkana — siblings/courage.

    3 parts of 10°. 1st = same sign, 2nd = 5th from sign, 3rd = 9th.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / 10) % 3
    offsets = [0, 4, 8]  # same, 5th, 9th
    return (ri + offsets[part]) % 12


def _d4(lon: float) -> int:
    """D4 Chaturthamsha — property/fortune.

    4 parts of 7°30'. Odd signs start from same sign, even from 10th.
    Each part advances by 3 signs.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / 7.5) % 4
    start = ri if _is_odd_rashi(ri) else (ri + 9) % 12
    return (start + part * 3) % 12


def _d5(lon: float) -> int:
    """D5 Panchamsha — spiritual merit.

    5 parts of 6°. Odd signs from same sign, even from opposite.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / 6) % 5
    start = ri if _is_odd_rashi(ri) else (ri + 6) % 12
    return (start + part) % 12


def _d7(lon: float) -> int:
    """D7 Saptamsha — children.

    7 parts of 4°17'8.57". Odd signs start from same sign,
    even signs start from 7th sign.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / (30 / 7)) % 7
    start = ri if _is_odd_rashi(ri) else (ri + 6) % 12
    return (start + part) % 12


def _d9(lon: float) -> int:
    """D9 Navamsa — soul/marriage.

    9 parts of 3°20'. Starting rashi by element:
    Fire → Mesha, Earth → Makara, Air → Tula, Water → Karka.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / (30 / 9)) % 9
    element_starts = {
        0: 0, 1: 9, 2: 6, 3: 3,     # Mesha, Vrishabha, Mithuna, Karka
        4: 0, 5: 9, 6: 6, 7: 3,     # Simha, Kanya, Tula, Vrischika
        8: 0, 9: 9, 10: 6, 11: 3,   # Dhanu, Makara, Kumbha, Meena
    }
    start = element_starts[ri]
    return (start + part) % 12


def _d10(lon: float) -> int:
    """D10 Dashamsha — career/profession.

    10 parts of 3°. Odd signs start from same sign,
    even signs start from 9th sign.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / 3) % 10
    start = ri if _is_odd_rashi(ri) else (ri + 8) % 12
    return (start + part) % 12


def _d12(lon: float) -> int:
    """D12 Dwadashamsha — parents.

    12 parts of 2°30'. Starts from same sign, each part = next sign.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / 2.5) % 12
    return (ri + part) % 12


def _d16(lon: float) -> int:
    """D16 Shodashamsha — vehicles/comforts.

    16 parts of 1°52'30". Starting sign by quality:
    Chara → Mesha, Sthira → Simha, Dwiswabhava → Dhanu.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / (30 / 16)) % 16
    quality = RASHI_QUALITIES[RASHIS[ri]]
    starts = {"Chara": 0, "Sthira": 4, "Dwiswabhava": 8}
    return (starts[quality] + part) % 12


def _d20(lon: float) -> int:
    """D20 Vimshamsha — spiritual progress.

    20 parts of 1°30'. Starting by quality:
    Chara → Mesha, Sthira → Dhanu, Dwiswabhava → Simha.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / 1.5) % 20
    quality = RASHI_QUALITIES[RASHIS[ri]]
    starts = {"Chara": 0, "Sthira": 8, "Dwiswabhava": 4}
    return (starts[quality] + part) % 12


def _d24(lon: float) -> int:
    """D24 Chaturvimshamsha — education/learning.

    24 parts of 1°15'. Odd signs from Simha, even from Karka.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / 1.25) % 24
    start = 4 if _is_odd_rashi(ri) else 3  # Simha / Karka
    return (start + part) % 12


def _d27(lon: float) -> int:
    """D27 Saptavimshamsha — strength/vitality.

    27 parts of 1°6'40". Starting by element:
    Fire → Mesha, Earth → Karka, Air → Tula, Water → Makara.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / (30 / 27)) % 27
    element_starts = {
        0: 0, 1: 3, 2: 6, 3: 9,     # Fire, Earth, Air, Water
        4: 0, 5: 3, 6: 6, 7: 9,
        8: 0, 9: 3, 10: 6, 11: 9,
    }
    start = element_starts[ri]
    return (start + part) % 12


def _d30(lon: float) -> int:
    """D30 Trimshamsha — misfortunes/evils.

    Unequal division (5 parts per sign):
    Odd signs: Mars(5°), Saturn(5°), Jupiter(8°), Mercury(7°), Venus(5°)
    Even signs: Venus(5°), Mercury(7°), Jupiter(8°), Saturn(5°), Mars(5°)

    The lordship determines the rashi: Mars=Mesha, Saturn=Kumbha,
    Jupiter=Dhanu, Mercury=Mithuna, Venus=Tula.
    """
    ri = _rashi_idx(lon)
    deg = _deg_in_rashi(lon)
    odd = _is_odd_rashi(ri)

    lord_to_rashi = {
        "Mars": 0, "Saturn": 10, "Jupiter": 8,
        "Mercury": 2, "Venus": 6,
    }

    if odd:
        bounds = [(5, "Mars"), (10, "Saturn"), (18, "Jupiter"),
                  (25, "Mercury"), (30, "Venus")]
    else:
        bounds = [(5, "Venus"), (12, "Mercury"), (20, "Jupiter"),
                  (25, "Saturn"), (30, "Mars")]

    for limit, lord in bounds:
        if deg < limit:
            return lord_to_rashi[lord]
    return lord_to_rashi[bounds[-1][1]]


def _d40(lon: float) -> int:
    """D40 Khavedamsha — auspicious effects.

    40 parts of 0°45'. Odd signs from Mesha, even from Tula.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / 0.75) % 40
    start = 0 if _is_odd_rashi(ri) else 6  # Mesha / Tula
    return (start + part) % 12


def _d60(lon: float) -> int:
    """D60 Shashtiamsha — past life karma.

    60 parts of 0°30'. Starts from same sign.
    """
    ri = _rashi_idx(lon)
    part = int(_deg_in_rashi(lon) / 0.5) % 60
    return (ri + part) % 12


# Dispatch table
_VARGA_FUNCS = {
    1: _d1, 2: _d2, 3: _d3, 4: _d4, 5: _d5, 7: _d7,
    9: _d9, 10: _d10, 12: _d12, 16: _d16, 20: _d20,
    24: _d24, 27: _d27, 30: _d30, 40: _d40, 60: _d60,
}

ALL_VARGA_DIVISIONS = sorted(_VARGA_FUNCS.keys())


# ===== Public API =====

def calculate_varga(chart: Chart, division: int) -> VargaChart:
    """Calculate a specific divisional chart.

    Args:
        chart: Natal chart with planet positions.
        division: D-number (1, 2, 3, 4, 5, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 60).

    Returns:
        VargaChart with positions for all planets and lagna.
    """
    func = _VARGA_FUNCS.get(division)
    if not func:
        raise ValueError(f"Unsupported varga division: D{division}")

    label = VARGA_LABELS.get(division, f"D{division}")

    # Lagna in this varga
    lagna_varga_idx = func(chart.lagna.longitude)

    positions = []
    # Lagna
    positions.append(VargaPosition(
        name="Lagna", rashi_idx=lagna_varga_idx,
        rashi=RASHIS[lagna_varga_idx], house=1,
    ))

    # Planets
    for planet in chart.planets:
        varga_idx = func(planet.longitude)
        house = ((varga_idx - lagna_varga_idx) % 12) + 1
        positions.append(VargaPosition(
            name=planet.name, rashi_idx=varga_idx,
            rashi=RASHIS[varga_idx], house=house,
        ))

    return VargaChart(
        division=division, label=label,
        lagna_rashi_idx=lagna_varga_idx, positions=positions,
    )


def calculate_all_vargas(chart: Chart) -> dict[int, VargaChart]:
    """Calculate all 16 divisional charts."""
    return {d: calculate_varga(chart, d) for d in ALL_VARGA_DIVISIONS}


def get_varga_rashi(longitude: float, division: int) -> tuple[int, str]:
    """Get varga rashi for a single longitude (utility)."""
    func = _VARGA_FUNCS.get(division)
    if not func:
        raise ValueError(f"Unsupported varga division: D{division}")
    idx = func(longitude)
    return idx, RASHIS[idx]
