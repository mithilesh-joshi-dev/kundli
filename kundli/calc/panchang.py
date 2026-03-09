"""Panchang (five-limb) calculations: Tithi, Nakshatra, Yoga, Karana, Vara."""

from datetime import datetime, timedelta, timezone

import swisseph as swe

from .constants import AYANAMSHA, KARANAS, TITHIS, WEEKDAYS


def calculate_panchang(year: int, month: int, day: int,
                       hour: int, minute: int, second: int,
                       utc_offset: float) -> dict:
    """Calculate Panchang elements for given date/time."""
    local = datetime(year, month, day, hour, minute, second,
                     tzinfo=timezone(timedelta(hours=utc_offset)))
    utc = local.astimezone(timezone.utc)
    utc_hour = utc.hour + utc.minute / 60 + utc.second / 3600
    jd = swe.julday(utc.year, utc.month, utc.day, utc_hour)

    swe.set_ephe_path(None)
    swe.set_sid_mode(AYANAMSHA)

    # Sun and Moon tropical longitudes (for tithi)
    sun_trop = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)[0][0]
    moon_trop = swe.calc_ut(jd, swe.MOON, swe.FLG_SWIEPH)[0][0]

    # Sun and Moon sidereal longitudes (for yoga)
    sun_sid = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
    moon_sid = swe.calc_ut(jd, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]

    # Vara (weekday) - Python weekday: Monday=0
    weekday_idx = local.weekday()
    vara = WEEKDAYS[weekday_idx]

    # Tithi: based on Moon - Sun angular distance
    # Each tithi = 12 degrees of Moon-Sun elongation
    diff = (moon_trop - sun_trop) % 360
    tithi_idx = int(diff / 12)
    tithi_name = TITHIS[tithi_idx]
    paksha = "Shukla" if tithi_idx < 15 else "Krishna"
    tithi_num = (tithi_idx % 15) + 1

    # Yoga: Sum of sidereal Sun and Moon longitudes / (360/27)
    yoga_sum = (sun_sid + moon_sid) % 360
    yoga_idx = int(yoga_sum / (360 / 27))
    yoga_names = (
        "Vishkumbha", "Preeti", "Ayushman", "Saubhagya", "Shobhana",
        "Atiganda", "Sukarma", "Dhriti", "Shoola", "Ganda",
        "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
        "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
        "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma",
        "Indra", "Vaidhriti",
    )
    yoga = yoga_names[yoga_idx % 27]

    # Karana: half-tithi, 60 karanas in a lunar month
    # First karana of a tithi
    karana_idx = int(diff / 6)  # each karana = 6 degrees
    # Fixed karanas: Shakuni(57), Chatushpada(58), Nagava(59), Kimstughna(0)
    if karana_idx == 0:
        karana = "Kimstughna"
    elif karana_idx >= 57:
        fixed_karanas = {57: "Shakuni", 58: "Chatushpada", 59: "Nagava"}
        karana = fixed_karanas[karana_idx]
    else:
        # Repeating cycle of 7 karanas (Bava to Vishti)
        karana = KARANAS[(karana_idx - 1) % 7]

    swe.close()

    return {
        "vara": vara,
        "tithi": f"{paksha} {tithi_name}" if tithi_num <= 14 else tithi_name,
        "tithi_num": tithi_num,
        "paksha": paksha,
        "yoga": yoga,
        "karana": karana,
    }
