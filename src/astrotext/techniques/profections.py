"""Annual profections (M3) — Hellenistic whole-sign time-lords.

Conventions (Vettius Valens; C. Brennan, *Hellenistic Astrology*):
* Year N (from birth) profects the ASC by N signs; the year lord is the
  domicile ruler of the profected sign.
* Year boundaries are the ACTUAL solar returns (astronomically exact
  anniversaries), not calendar dates — the difference can reach a day.
* Monthly profections: the profection year is divided into 12 equal parts
  (variant: calendar months — documented; equal-division is deterministic
  and closest to the solar logic).  Month 0 starts at the year's profected
  sign and advances one sign per month.
* Other points (MC, Fortune) profect at the same rate; we report ASC (the
  master cycle), plus profected MC and Fortune signs for the current year.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.chart import Chart, default_ephemeris
from ..core.dignities import DOMICILE
from ..core.zodiac import SIGNS_ABBR, sign_index
from ..ephem.engine import Ephemeris
from ..timespace.moment import Moment
from .search import angular_roots

__all__ = ["ProfectionYear", "ProfectionsReport", "profections"]


@dataclass(frozen=True, slots=True)
class ProfectionYear:
    age: int
    start_jd: float             # solar return (age-th anniversary)
    end_jd: float
    asc_sign: int               # profected ASC sign index
    year_lord: str


@dataclass(frozen=True, slots=True)
class ProfectionsReport:
    natal: Chart
    years: list[ProfectionYear]         # full table from birth
    current: ProfectionYear | None      # the year containing `target`
    current_month_index: int | None     # 0..11
    current_month_sign: int | None
    current_month_lord: str | None
    profected_mc_sign: int | None
    profected_fortune_sign: int | None


def _solar_return_boundaries(natal: Chart, up_to_jd: float,
                             eph: Ephemeris) -> list[float]:
    """[birth, SR1, SR2, ...] strictly increasing, covering up_to_jd."""
    birth = natal.moment.jd_ut
    natal_sun = natal.points["SUN"].lon
    horizon = up_to_jd + 400.0
    roots = angular_roots(lambda t: eph.lon(t, "SUN"), natal_sun,
                          birth + 300.0, horizon, 12.0)
    return [birth] + roots


def profections(
    natal: Chart,
    target: Moment,
    eph: Ephemeris | None = None,
    max_years: int | None = None,
) -> ProfectionsReport:
    if natal.angles is None:
        raise ValueError("profections need the natal ASC; birth time unknown -> undefined")
    eph = eph or default_ephemeris()
    birth_jd = natal.moment.jd_ut
    if target.jd_ut < birth_jd:
        raise ValueError("target predates birth")

    bounds = _solar_return_boundaries(natal, target.jd_ut, eph)
    asc_sign = sign_index(natal.angles["ASC"])

    years: list[ProfectionYear] = []
    for age in range(len(bounds) - 1):
        s = (asc_sign + age) % 12
        years.append(ProfectionYear(
            age=age, start_jd=bounds[age], end_jd=bounds[age + 1],
            asc_sign=s, year_lord=DOMICILE[s]))
    if max_years is not None:
        years = years[:max_years]

    current = next((y for y in years
                    if y.start_jd <= target.jd_ut < y.end_jd), None)
    mi = ms = None
    ml = None
    mc_s = fo_s = None
    if current is not None:
        span = current.end_jd - current.start_jd
        mi = min(11, int((target.jd_ut - current.start_jd) / (span / 12.0)))
        ms = (current.asc_sign + mi) % 12
        ml = DOMICILE[ms]
        mc_s = (sign_index(natal.angles["MC"]) + current.age) % 12
        if "FORTUNE" in natal.lots:
            fo_s = (sign_index(natal.lots["FORTUNE"]) + current.age) % 12
    return ProfectionsReport(
        natal=natal, years=years, current=current,
        current_month_index=mi, current_month_sign=ms, current_month_lord=ml,
        profected_mc_sign=mc_s, profected_fortune_sign=fo_s,
    )
