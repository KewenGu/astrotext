"""Fixed stars — conjunctions (by ecliptic longitude) to points and angles.

The traditional technique uses tight longitude conjunctions only; 1 degree
default orb.  Star positions come from Swiss Ephemeris' sefstars.txt
(vendored with the ephemeris files).
"""
from __future__ import annotations

from dataclasses import dataclass

import swisseph as swe

from .angles import angdiff

__all__ = ["MAJOR_STARS", "StarHit", "star_hits"]

#: the working list: bright + traditionally loaded stars
MAJOR_STARS: tuple[str, ...] = (
    "Algol", "Alcyone", "Aldebaran", "Rigel", "Capella", "Betelgeuse",
    "Sirius", "Canopus", "Castor", "Pollux", "Procyon", "Alphard",
    "Regulus", "Denebola", "Spica", "Arcturus", "Antares",
    "Vega", "Altair", "Fomalhaut", "Deneb Algedi", "Achernar",
)


@dataclass(frozen=True, slots=True)
class StarHit:
    star: str
    star_lon: float
    target: str
    delta: float          # star_lon - target_lon, signed, within orb


def star_positions(jd_ut: float, stars: tuple[str, ...] = MAJOR_STARS
                   ) -> dict[str, float]:
    out: dict[str, float] = {}
    for name in stars:
        xx, _retname, _flg = swe.fixstar_ut(name, jd_ut, swe.FLG_SWIEPH)
        out[name] = xx[0]
    return out


def star_hits(jd_ut: float, targets: dict[str, float], orb: float = 1.0,
              stars: tuple[str, ...] = MAJOR_STARS) -> list[StarHit]:
    """Deterministic order: star list order, then target insertion order."""
    pos = star_positions(jd_ut, stars)
    hits: list[StarHit] = []
    for name in stars:
        for tkey, tlon in targets.items():
            d = angdiff(pos[name], tlon)
            if abs(d) <= orb:
                hits.append(StarHit(star=name, star_lon=pos[name],
                                    target=tkey, delta=d))
    return hits
