"""Nakshatra attributes: Yoni, Gana, Varna, Nadi for matching."""

# Index matches NAKSHATRAS tuple order (0=Ashwini, 26=Revati)

# Gana: Deva, Manushya, Rakshasa
NAKSHATRA_GANA = (
    "Deva",      # Ashwini
    "Manushya",  # Bharani
    "Rakshasa",  # Krittika
    "Manushya",  # Rohini
    "Deva",      # Mrigashira
    "Manushya",  # Ardra
    "Deva",      # Punarvasu
    "Deva",      # Pushya
    "Rakshasa",  # Ashlesha
    "Rakshasa",  # Magha
    "Manushya",  # Purva Phalguni
    "Manushya",  # Uttara Phalguni
    "Deva",      # Hasta
    "Rakshasa",  # Chitra
    "Deva",      # Swati
    "Rakshasa",  # Vishakha
    "Deva",      # Anuradha
    "Rakshasa",  # Jyeshtha
    "Rakshasa",  # Moola
    "Manushya",  # Purva Ashadha
    "Manushya",  # Uttara Ashadha
    "Deva",      # Shravana
    "Rakshasa",  # Dhanishta
    "Rakshasa",  # Shatabhisha
    "Manushya",  # Purva Bhadrapada
    "Manushya",  # Uttara Bhadrapada
    "Deva",      # Revati
)

# Yoni (animal pair) - each nakshatra has a male or female yoni
# Format: (animal, gender)
NAKSHATRA_YONI = (
    ("Horse", "M"),        # Ashwini
    ("Elephant", "M"),     # Bharani
    ("Goat", "F"),         # Krittika
    ("Serpent", "M"),      # Rohini
    ("Serpent", "F"),      # Mrigashira
    ("Dog", "F"),          # Ardra
    ("Cat", "F"),          # Punarvasu
    ("Goat", "M"),         # Pushya
    ("Cat", "M"),          # Ashlesha
    ("Rat", "M"),          # Magha
    ("Rat", "F"),          # Purva Phalguni
    ("Cow", "M"),          # Uttara Phalguni
    ("Buffalo", "F"),      # Hasta
    ("Tiger", "F"),        # Chitra
    ("Buffalo", "M"),      # Swati
    ("Tiger", "M"),        # Vishakha
    ("Deer", "F"),         # Anuradha
    ("Deer", "M"),         # Jyeshtha
    ("Dog", "M"),          # Moola
    ("Monkey", "M"),       # Purva Ashadha
    ("Mongoose", "M"),     # Uttara Ashadha
    ("Monkey", "F"),       # Shravana
    ("Lion", "F"),         # Dhanishta
    ("Horse", "F"),        # Shatabhisha
    ("Lion", "M"),         # Purva Bhadrapada
    ("Cow", "F"),          # Uttara Bhadrapada
    ("Elephant", "F"),     # Revati
)

# Yoni compatibility matrix (animal enemies)
YONI_ENEMIES = {
    "Horse": "Buffalo",
    "Buffalo": "Horse",
    "Elephant": "Lion",
    "Lion": "Elephant",
    "Dog": "Deer",
    "Deer": "Dog",
    "Cat": "Rat",
    "Rat": "Cat",
    "Serpent": "Mongoose",
    "Mongoose": "Serpent",
    "Monkey": "Goat",
    "Goat": "Monkey",
    "Cow": "Tiger",
    "Tiger": "Cow",
}

# Nadi: Aadi (Vata), Madhya (Pitta), Antya (Kapha)
NAKSHATRA_NADI = (
    "Aadi",    # Ashwini
    "Madhya",  # Bharani
    "Antya",   # Krittika
    "Antya",   # Rohini
    "Madhya",  # Mrigashira
    "Aadi",    # Ardra
    "Aadi",    # Punarvasu
    "Madhya",  # Pushya
    "Antya",   # Ashlesha
    "Antya",   # Magha
    "Madhya",  # Purva Phalguni
    "Aadi",    # Uttara Phalguni
    "Aadi",    # Hasta
    "Madhya",  # Chitra
    "Antya",   # Swati
    "Antya",   # Vishakha
    "Madhya",  # Anuradha
    "Aadi",    # Jyeshtha
    "Aadi",    # Moola
    "Madhya",  # Purva Ashadha
    "Antya",   # Uttara Ashadha
    "Antya",   # Shravana
    "Madhya",  # Dhanishta
    "Aadi",    # Shatabhisha
    "Aadi",    # Purva Bhadrapada
    "Madhya",  # Uttara Bhadrapada
    "Antya",   # Revati
)

# Varna: Brahmin, Kshatriya, Vaishya, Shudra
NAKSHATRA_VARNA = (
    "Kshatriya",  # Ashwini
    "Shudra",     # Bharani
    "Brahmin",    # Krittika
    "Shudra",     # Rohini
    "Vaishya",    # Mrigashira
    "Shudra",     # Ardra
    "Vaishya",    # Punarvasu
    "Kshatriya",  # Pushya
    "Shudra",     # Ashlesha
    "Shudra",     # Magha
    "Brahmin",    # Purva Phalguni
    "Kshatriya",  # Uttara Phalguni
    "Vaishya",    # Hasta
    "Shudra",     # Chitra
    "Brahmin",    # Swati
    "Shudra",     # Vishakha
    "Shudra",     # Anuradha
    "Vaishya",    # Jyeshtha
    "Shudra",     # Moola
    "Brahmin",    # Purva Ashadha
    "Kshatriya",  # Uttara Ashadha
    "Shudra",     # Shravana
    "Vaishya",    # Dhanishta
    "Shudra",     # Shatabhisha
    "Brahmin",    # Purva Bhadrapada
    "Kshatriya",  # Uttara Bhadrapada
    "Shudra",     # Revati
)

# Vashya groups based on rashi
RASHI_VASHYA = {
    "Mesha": "Chatushpada",
    "Vrishabha": "Chatushpada",
    "Mithuna": "Nara",
    "Karka": "Keeta",
    "Simha": "Vanachara",
    "Kanya": "Nara",
    "Tula": "Nara",
    "Vrischika": "Keeta",
    "Dhanu": "Chatushpada",  # first half Nara, second half Chatushpada
    "Makara": "Jalchar",     # first half Chatushpada, second half Jalchar
    "Kumbha": "Nara",
    "Meena": "Jalchar",
}

# Bhakoot (Rashi) compatibility - unfavorable pairs (house distances)
# 6-8, 2-12, 9-5 from each other are considered inauspicious
BHAKOOT_BAD_PAIRS = {(2, 12), (12, 2), (6, 8), (8, 6), (5, 9), (9, 5)}


def get_nakshatra_attrs(nak_idx: int) -> dict:
    """Get all attributes for a nakshatra by index."""
    animal, gender = NAKSHATRA_YONI[nak_idx]
    return {
        "gana": NAKSHATRA_GANA[nak_idx],
        "yoni": animal,
        "yoni_gender": gender,
        "nadi": NAKSHATRA_NADI[nak_idx],
        "varna": NAKSHATRA_VARNA[nak_idx],
    }
