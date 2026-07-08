"""Firdaria (Persian time-lords) — M3.

Conventions (Abu Ma'shar / Ben Dykes, *Persian Nativities*):
* 75-year cycle.  Major periods (years):
    Sun 10, Venus 8, Mercury 13, Moon 9, Saturn 11, Jupiter 12, Mars 7,
    North Node 3, South Node 2                                  (= 75)
* DAY births start from the Sun, NIGHT births from the Moon, continuing in
  the same circular planet order.
* Node placement variants:
    'after-mars' (default, the Dykes/Persian rule): the two node periods
      always follow Mars, wherever Mars falls in the sequence.
    'at-end': nodes appended after the seven planets.
  For day births the two variants coincide.
* Each PLANET period splits into 7 equal sub-periods, first sub-lord = the
  major lord, then the circular planet order.  Node periods have no subs.
* Year length: tropical year by default ('julian' knob available) — tables
  built on calendar anniversaries can differ by a few days; documented.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.chart import Chart
from .progressions import YEAR_LENGTHS

__all__ = ["FirdariaPeriod", "firdaria", "MAJOR_YEARS", "PLANET_ORDER"]

PLANET_ORDER = ["SUN", "VENUS", "MERCURY", "MOON", "SATURN", "JUPITER", "MARS"]
MAJOR_YEARS = {"SUN": 10, "VENUS": 8, "MERCURY": 13, "MOON": 9,
               "SATURN": 11, "JUPITER": 12, "MARS": 7,
               "NORTH_NODE": 3, "SOUTH_NODE": 2}


@dataclass(frozen=True, slots=True)
class FirdariaPeriod:
    level: int              # 1 = major, 2 = sub
    lord: str
    start_jd: float
    end_jd: float
    start_age: float        # years since birth
    end_age: float
    major_lord: str | None = None   # for subs


def _sequence(is_day: bool, nodes: str) -> list[str]:
    start = 0 if is_day else PLANET_ORDER.index("MOON")
    planets = [PLANET_ORDER[(start + i) % 7] for i in range(7)]
    if nodes == "after-mars":
        i = planets.index("MARS") + 1
        return planets[:i] + ["NORTH_NODE", "SOUTH_NODE"] + planets[i:]
    if nodes == "at-end":
        return planets + ["NORTH_NODE", "SOUTH_NODE"]
    raise ValueError(f"nodes must be 'after-mars' or 'at-end', got {nodes!r}")


def firdaria(
    natal: Chart,
    cycles: int = 2,
    nodes: str = "after-mars",
    year: str = "tropical",
) -> list[FirdariaPeriod]:
    """The full timeline from birth: ``cycles`` x 75 years of majors + subs.

    Requires a known sect; unknown-birth-time charts (is_day None) raise —
    a wrong sect flips the whole sequence, so guessing is forbidden.
    """
    if natal.is_day is None:
        raise ValueError("firdaria needs sect; birth time unknown -> undefined")
    ylen = YEAR_LENGTHS[year]
    birth = natal.moment.jd_ut
    seq = _sequence(natal.is_day, nodes)
    assert sum(MAJOR_YEARS[x] for x in seq) == 75

    out: list[FirdariaPeriod] = []
    age = 0.0
    for _cycle in range(cycles):
        for lord in seq:
            yrs = MAJOR_YEARS[lord]
            start, end = age, age + yrs
            out.append(FirdariaPeriod(
                1, lord, birth + start * ylen, birth + end * ylen, start, end))
            if lord in PLANET_ORDER:  # planets get 7 subs; nodes don't
                sub_len = yrs / 7.0
                base = PLANET_ORDER.index(lord)
                for j in range(7):
                    s = age + j * sub_len
                    e = s + sub_len
                    out.append(FirdariaPeriod(
                        2, PLANET_ORDER[(base + j) % 7],
                        birth + s * ylen, birth + e * ylen, s, e, lord))
            age = end
    return out
