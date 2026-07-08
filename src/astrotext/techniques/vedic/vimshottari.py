"""Vimshottari dasha — the 120-year nakshatra-based time-lord system.

Rules (BPHS; universal across software):
* Lord years: Ketu 7, Venus 20, Sun 6, Moon 10, Mars 7, Rahu 18,
  Jupiter 16, Saturn 19, Mercury 17  (= 120).
* The first mahadasha lord is the lord of the natal MOON's nakshatra; the
  balance at birth is the UNELAPSED fraction of that nakshatra times the
  lord's years.  Subsequent lords follow the fixed sequence.
* Sub-periods (antardasha) divide the parent proportionally to each lord's
  years/120, starting from the parent's own lord; pratyantardasha nests the
  same way.  Every level spans its parent gaplessly.
* Year length: 365.25 days by default (mainstream software convention);
  knob for the tropical year.
"""
from __future__ import annotations

from dataclasses import dataclass

from .nakshatra import VIMSHOTTARI_LORDS, of as nakshatra_of

__all__ = ["DASHA_YEARS", "DashaPeriod", "vimshottari"]

DASHA_YEARS = {"KETU": 7, "VENUS": 20, "SUN": 6, "MOON": 10, "MARS": 7,
               "RAHU": 18, "JUPITER": 16, "SATURN": 19, "MERCURY": 17}

TOTAL_YEARS = 120


@dataclass(frozen=True, slots=True)
class DashaPeriod:
    level: int                  # 1 maha, 2 antar, 3 pratyantar
    lords: tuple[str, ...]      # lineage, e.g. ("VENUS", "SUN", "MOON")
    start_jd: float
    end_jd: float

    @property
    def lord(self) -> str:
        return self.lords[-1]


def _seq_from(lord: str) -> list[str]:
    i = VIMSHOTTARI_LORDS.index(lord)
    return [VIMSHOTTARI_LORDS[(i + k) % 9] for k in range(9)]


def _subdivide(parent: DashaPeriod, max_level: int,
               out: list[DashaPeriod]) -> None:
    if parent.level >= max_level:
        return
    span = parent.end_jd - parent.start_jd
    t = parent.start_jd
    for lord in _seq_from(parent.lord):
        frac = DASHA_YEARS[lord] / TOTAL_YEARS
        child = DashaPeriod(level=parent.level + 1,
                            lords=parent.lords + (lord,),
                            start_jd=t, end_jd=t + span * frac)
        out.append(child)
        _subdivide(child, max_level, out)
        t = child.end_jd


def vimshottari(
    moon_sid_lon: float,
    birth_jd_ut: float,
    year_days: float = 365.25,
    cycles_years: float = 120.0,
    max_level: int = 3,
) -> list[DashaPeriod]:
    """The full nested timeline from birth for one 120-year cycle.

    Returned depth-first (each maha followed by its antars, each antar by
    its pratyantars) — the natural reading order for a timeline.
    """
    nak = nakshatra_of(moon_sid_lon)
    first_lord = nak.lord
    balance_frac = 1.0 - nak.fraction          # unelapsed part of the nakshatra

    out: list[DashaPeriod] = []
    # The first mahadasha started BEFORE birth: reconstruct its true span so
    # sub-periods are exact, then clip nothing — periods before birth simply
    # lie before birth_jd (renderers mark the birth balance explicitly).
    first_years = DASHA_YEARS[first_lord]
    start_offset_years = (1.0 - balance_frac) * first_years
    t = birth_jd_ut - start_offset_years * year_days

    elapsed_years = -start_offset_years
    for lord in _seq_from(first_lord):
        if elapsed_years >= cycles_years:
            break
        yrs = DASHA_YEARS[lord]
        p = DashaPeriod(level=1, lords=(lord,),
                        start_jd=t, end_jd=t + yrs * year_days)
        out.append(p)
        _subdivide(p, max_level, out)
        t = p.end_jd
        elapsed_years += yrs
    return out
