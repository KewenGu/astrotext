"""Progressions & directions (M2).

Conventions (docs/TECHNIQUES.md):

* SECONDARY: 1 civil day after birth = 1 year of life.
  Year length knob: 'tropical' 365.242198781d (default; the astro.com
  convention) or 'julian' 365.25d.
  progressed_jd = natal_jd + elapsed_days / year_length

* TERTIARY (Troinski I): 1 civil day = 1 month.
  Month knob: 'tropical' 27.321582241d (default) or 'sidereal' 27.321661547d.

* MINOR: 1 month of ephemeris time = 1 year of life (month knob as above).

* SOLAR ARC: every natal point advanced by the secondary progressed Sun's
  arc.  arc = lon(Sun, progressed_jd) - lon(Sun, natal_jd)  (wrap-safe,
  monotonically growing ~1 deg/year).

* Progressed angles, two methods:
    'solar-arc-mc'  (default): progressed MC = natal MC + solar arc
      (ecliptic); ASC/cusps recomputed from the progressed MC's ARMC at the
      natal latitude and progressed obliquity.  This is the widespread
      "MC by solar arc" convention.
    'chart'         : simply the chart of the progressed JD at the birth
      place (quotidian-style angles; they sweep the whole zodiac yearly).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import swisseph as swe

from ..core.angles import angdiff, norm360
from ..core.chart import Chart, compute_chart, default_ephemeris
from ..core.settings import Settings
from ..ephem.engine import Ephemeris
from ..timespace.moment import Moment, from_utc
from ..timespace.place import Place

__all__ = [
    "YEAR_LENGTHS", "MONTH_LENGTHS",
    "secondary_jd", "tertiary_jd", "minor_jd", "progressed_moment",
    "solar_arc", "ProgressedAngles", "progressed_angles_solar_arc_mc",
]

YEAR_LENGTHS = {"tropical": 365.242198781, "julian": 365.25}
MONTH_LENGTHS = {"tropical": 27.321582241, "sidereal": 27.321661547}


def _elapsed_days(natal: Moment, target_jd_ut: float) -> float:
    d = target_jd_ut - natal.jd_ut
    if d < 0:
        raise ValueError(f"target predates birth by {-d:.2f} days")
    return d


def secondary_jd(natal: Moment, target_jd_ut: float,
                 year: str = "tropical") -> float:
    return natal.jd_ut + _elapsed_days(natal, target_jd_ut) / YEAR_LENGTHS[year]


def tertiary_jd(natal: Moment, target_jd_ut: float,
                month: str = "tropical") -> float:
    return natal.jd_ut + _elapsed_days(natal, target_jd_ut) / MONTH_LENGTHS[month]


def minor_jd(natal: Moment, target_jd_ut: float, month: str = "tropical",
             year: str = "tropical") -> float:
    """1 month of ephemeris motion per year of life."""
    years = _elapsed_days(natal, target_jd_ut) / YEAR_LENGTHS[year]
    return natal.jd_ut + years * MONTH_LENGTHS[month]


def progressed_moment(natal: Moment, prog_jd_ut: float) -> Moment:
    """A Moment at the progressed JD, anchored at the birth place."""
    import datetime as dt
    y, mo, d, h = swe.revjul(prog_jd_ut, swe.GREG_CAL)
    hh = int(h); mi = int((h - hh) * 60); ss = (h - hh) * 3600 - mi * 60
    micro = min(999999, max(0, round((ss - int(ss)) * 1e6)))
    utc = dt.datetime(y, mo, d, hh, mi, int(ss), micro, tzinfo=dt.timezone.utc)
    return from_utc(utc, natal.place)


def solar_arc(natal: Moment, target_jd_ut: float, year: str = "tropical",
              eph: Ephemeris | None = None) -> float:
    """The secondary progressed Sun's arc, in [0, 360) (wrap-safe: reaches
    ~120 deg only after ~120 years, far below 360)."""
    eph = eph or default_ephemeris()
    pjd = secondary_jd(natal, target_jd_ut, year)
    sun_natal = eph.state(natal.jd_ut, "SUN").lon
    sun_prog = eph.state(pjd, "SUN").lon
    arc = norm360(sun_prog - sun_natal)
    return arc


@dataclass(frozen=True, slots=True)
class ProgressedAngles:
    method: str
    mc: float
    asc: float
    armc: float
    cusps: tuple[float, ...]
    obliquity: float


def _armc_from_mc(mc: float, eps: float) -> float:
    """Ecliptic MC -> ARMC (right ascension of the meridian)."""
    rad = math.radians
    armc = math.degrees(math.atan2(math.sin(rad(mc)) * math.cos(rad(eps)),
                                   math.cos(rad(mc))))
    return norm360(armc)


def progressed_angles_solar_arc_mc(
    natal_chart: Chart, prog_jd_ut: float, arc: float,
    hsys: str | None = None,
) -> ProgressedAngles:
    """'MC by solar arc': add the arc to the natal MC on the ecliptic, then
    rebuild ASC/cusps from the corresponding ARMC at natal latitude with the
    obliquity of the progressed date."""
    if natal_chart.angles is None:
        raise ValueError("natal chart has no angles (unknown birth time?)")
    ecl, _ = swe.calc_ut(prog_jd_ut, swe.ECL_NUT, 0)
    eps = ecl[0]
    mc = norm360(natal_chart.angles["MC"] + arc)
    armc = _armc_from_mc(mc, eps)
    lat = natal_chart.moment.place.lat
    h = hsys or natal_chart.house_system_used or "P"
    try:
        cusps, ascmc = swe.houses_armc(armc, lat, eps, h.encode("ascii"))
    except Exception:
        cusps, ascmc = swe.houses_armc(armc, lat, eps, b"O")
        h = "O"
    return ProgressedAngles(method=f"solar-arc-mc/{h}", mc=mc, asc=ascmc[0],
                            armc=armc, cusps=tuple(cusps), obliquity=eps)
