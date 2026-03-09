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
