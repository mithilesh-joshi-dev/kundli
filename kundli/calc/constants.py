import swisseph as swe

RASHIS = (
    "Mesha", "Vrishabha", "Mithuna", "Karka",
    "Simha", "Kanya", "Tula", "Vrischika",
    "Dhanu", "Makara", "Kumbha", "Meena",
)

NAKSHATRAS = (
    "Ashwini", "Bharani", "Krittika", "Rohini",
    "Mrigashira", "Ardra", "Punarvasu", "Pushya",
    "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha",
    "Anuradha", "Jyeshtha", "Moola", "Purva Ashadha",
    "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
)

# Nakshatra lords for Vimshottari Dasha (future use)
NAKSHATRA_LORDS = (
    "Ketu", "Venus", "Sun", "Moon",
    "Mars", "Rahu", "Jupiter", "Saturn",
    "Mercury", "Ketu", "Venus", "Sun",
    "Moon", "Mars", "Rahu", "Jupiter",
    "Saturn", "Mercury", "Ketu", "Venus",
    "Sun", "Moon", "Mars", "Rahu",
    "Jupiter", "Saturn", "Mercury",
)

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
    "Ketu": None,  # Derived: Rahu + 180
}

AYANAMSHA = swe.SIDM_LAHIRI

# Rashi elements
RASHI_ELEMENTS = {
    "Mesha": "Fire", "Vrishabha": "Earth", "Mithuna": "Air", "Karka": "Water",
    "Simha": "Fire", "Kanya": "Earth", "Tula": "Air", "Vrischika": "Water",
    "Dhanu": "Fire", "Makara": "Earth", "Kumbha": "Air", "Meena": "Water",
}

# Rashi qualities
RASHI_QUALITIES = {
    "Mesha": "Chara", "Vrishabha": "Sthira", "Mithuna": "Dwiswabhava",
    "Karka": "Chara", "Simha": "Sthira", "Kanya": "Dwiswabhava",
    "Tula": "Chara", "Vrischika": "Sthira", "Dhanu": "Dwiswabhava",
    "Makara": "Chara", "Kumbha": "Sthira", "Meena": "Dwiswabhava",
}

# Weekday names
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# Tithi names
TITHIS = (
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima",
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Amavasya",
)

# Karana names (half-tithi)
KARANAS = (
    "Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti",
    "Shakuni", "Chatushpada", "Nagava", "Kimstughna",
)

# --- Shadbala constants (BPHS) ---

# Dig Bala: house where planet gets directional strength
DIG_BALA_HOUSES = {
    "Sun": 10, "Mars": 10,           # Strong in 10th (south)
    "Jupiter": 1, "Mercury": 1,      # Strong in 1st (east)
    "Moon": 4, "Venus": 4,           # Strong in 4th (north)
    "Saturn": 7,                      # Strong in 7th (west)
}

# Naisargika Bala: fixed natural strength in virupas (BPHS)
NAISARGIKA_BALA = {
    "Sun": 60.0, "Moon": 51.43, "Venus": 42.86,
    "Jupiter": 34.29, "Mercury": 25.71, "Mars": 17.14, "Saturn": 8.57,
}

# Minimum required Shadbala per planet (in virupas, BPHS)
SHADBALA_REQUIRED = {
    "Sun": 390, "Moon": 360, "Mars": 300,
    "Mercury": 420, "Jupiter": 390, "Venus": 330, "Saturn": 300,
}

# Mean daily motion (degrees/day) for Cheshta Bala
MEAN_DAILY_MOTION = {
    "Sun": 0.9856, "Moon": 13.1764, "Mars": 0.5240,
    "Mercury": 1.3833, "Jupiter": 0.0831, "Venus": 1.2000, "Saturn": 0.0335,
}

# Varga labels
VARGA_LABELS = {
    1: "Rashi", 2: "Hora", 3: "Drekkana", 4: "Chaturthamsha",
    5: "Panchamsha", 7: "Saptamsha", 9: "Navamsa", 10: "Dashamsha",
    12: "Dwadashamsha", 16: "Shodashamsha", 20: "Vimshamsha",
    24: "Chaturvimshamsha", 27: "Saptavimshamsha", 30: "Trimshamsha",
    40: "Khavedamsha", 60: "Shashtiamsha",
}
