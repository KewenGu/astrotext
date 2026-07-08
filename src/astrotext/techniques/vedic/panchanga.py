"""Panchanga — the five limbs of the Vedic day, from Sun/Moon longitudes.

All pure arithmetic on SIDEREAL longitudes (tithi/karana depend only on the
Sun-Moon difference and are ayanamsa-invariant; yoga uses the SUM, which is
not, so nirayana longitudes are required — the traditional convention).

* tithi   = floor((Moon - Sun) / 12deg), 30 per lunation, 2 paksas
* karana  = half-tithi; 60 per lunation: Kimstughna first, then the seven
            movable karanas cycling 8 times, then Shakuni, Chatushpada, Naga
* yoga    = floor((Sun + Moon) / 13deg20'), 27 names
* vara    = weekday (planetary day; computed by core.hours)
* the fifth limb is the Moon's nakshatra (see nakshatra.py)
Source: standard panchanga arithmetic (identical across traditions).
"""
from __future__ import annotations

from dataclasses import dataclass

from ...core.angles import norm360

__all__ = ["TITHIS", "KARANAS_MOVABLE", "YOGAS", "Panchanga", "compute"]

_TITHI_BASE = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
    "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
    "Trayodashi", "Chaturdashi",
]
TITHIS = (["Shukla " + n for n in _TITHI_BASE] + ["Purnima"]
          + ["Krishna " + n for n in _TITHI_BASE] + ["Amavasya"])

KARANAS_MOVABLE = ["Bava", "Balava", "Kaulava", "Taitila",
                   "Gara", "Vanija", "Vishti"]

YOGAS = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
    "Sukarman", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata",
    "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyan", "Parigha",
    "Shiva", "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra",
    "Vaidhriti",
]


def _karana_name(idx: int) -> str:
    """idx 0..59 within the lunation."""
    if idx == 0:
        return "Kimstughna"
    if idx >= 57:
        return ["Shakuni", "Chatushpada", "Naga"][idx - 57]
    return KARANAS_MOVABLE[(idx - 1) % 7]


@dataclass(frozen=True, slots=True)
class Panchanga:
    tithi_index: int          # 0..29
    tithi: str
    paksha: str               # Shukla (waxing) | Krishna (waning)
    tithi_fraction: float     # elapsed fraction of the tithi
    karana_index: int         # 0..59
    karana: str
    yoga_index: int           # 0..26
    yoga: str


def compute(sun_sid_lon: float, moon_sid_lon: float) -> Panchanga:
    elong = norm360(moon_sid_lon - sun_sid_lon)
    t_idx = min(29, int(elong // 12.0))
    k_idx = min(59, int(elong // 6.0))
    y_idx = min(26, int(norm360(sun_sid_lon + moon_sid_lon) // (360.0 / 27.0)))
    return Panchanga(
        tithi_index=t_idx, tithi=TITHIS[t_idx],
        paksha="Shukla" if elong < 180.0 else "Krishna",
        tithi_fraction=(elong - t_idx * 12.0) / 12.0,
        karana_index=k_idx, karana=_karana_name(k_idx),
        yoga_index=y_idx, yoga=YOGAS[y_idx],
    )
