"""Nakshatras — the 27 lunar mansions (sidereal longitudes).

Span 13°20' each, starting Ashwini at 0° sidereal Aries; 4 padas of 3°20'.
Lords follow the Vimshottari sequence starting Ketu at Ashwini
(Ketu, Venus, Sun, Moon, Mars, Rahu, Jupiter, Saturn, Mercury) x 3.
Source: standard Jyotish tables (BPHS; identical across traditions).
"""
from __future__ import annotations

from dataclasses import dataclass

from ...core.angles import norm360

__all__ = ["NAKSHATRAS", "VIMSHOTTARI_LORDS", "SPAN", "PADA", "Nakshatra", "of"]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
]

VIMSHOTTARI_LORDS = ["KETU", "VENUS", "SUN", "MOON", "MARS",
                     "RAHU", "JUPITER", "SATURN", "MERCURY"]

SPAN = 360.0 / 27.0          # 13 deg 20'
PADA = SPAN / 4.0            # 3 deg 20'


@dataclass(frozen=True, slots=True)
class Nakshatra:
    index: int               # 0..26
    name: str
    pada: int                # 1..4
    lord: str
    deg_in_nak: float        # [0, SPAN)
    fraction: float          # elapsed fraction of the nakshatra, [0, 1)


def of(sid_lon: float) -> Nakshatra:
    lon = norm360(sid_lon)
    idx = int(lon // SPAN) % 27
    within = lon - idx * SPAN
    return Nakshatra(
        index=idx, name=NAKSHATRAS[idx],
        pada=min(4, int(within // PADA) + 1),
        lord=VIMSHOTTARI_LORDS[idx % 9],
        deg_in_nak=within, fraction=within / SPAN,
    )
