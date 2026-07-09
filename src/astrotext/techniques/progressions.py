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

import numpy as np

from ..kernel import frames as _kfr
from ..kernel import houses as _kh
from ..kernel import timescales as _ts

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
    "ProgressedReport", "compute_progressed",
    "SolarArcReport", "compute_solar_arc", "TIGHT_MAJORS",
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
    """A Moment at the progressed JD, anchored at the birth place.

    Built DIRECTLY from the JD — no datetime round-trip: relabeling a UT1
    julian day as UTC and re-converting would shift it by (UT1-UTC) ~0.2s,
    which is exactly the kind of silent drift this engine forbids.  The
    datetime fields are display labels derived from the JD.
    """
    import datetime as dt
    delta_days = _ts.deltat(prog_jd_ut)
    y, mo, d, h = _ts.revjul(prog_jd_ut, _ts.GREGORIAN)
    hh = int(h); mi = int((h - hh) * 60); ss = (h - hh) * 3600 - mi * 60
    micro = min(999999, max(0, round((ss - int(ss)) * 1e6)))
    label = dt.datetime(y, mo, d, hh, mi, int(ss), micro, tzinfo=dt.timezone.utc)
    return Moment(
        local=label.replace(tzinfo=None), place=natal.place,
        calendar="gregorian", tz_used="UT", utc_offset=dt.timedelta(0),
        utc=label, jd_ut=prog_jd_ut, jd_tt=prog_jd_ut + delta_days,
        delta_t_sec=delta_days * 86400.0, flags=(),
    )


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
    # kernel house math is backend-free (exact swe_houses_armc parity, K4)
    eps = float(np.degrees(_kfr.true_obliquity(
        _ts.ut1_to_tt(prog_jd_ut, "swieph"))))
    mc = norm360(natal_chart.angles["MC"] + arc)
    armc = _armc_from_mc(mc, eps)
    lat = natal_chart.moment.place.lat
    h = hsys or natal_chart.house_system_used or "P"
    try:
        cusps = _kh.cusps(armc, eps, lat, h)
        ang = _kh.angles(armc, eps, lat)
    except _kh.PolarHousesError:
        h = "O"
        cusps = _kh.cusps(armc, eps, lat, h)
        ang = _kh.angles(armc, eps, lat)
    return ProgressedAngles(method=f"solar-arc-mc/{h}", mc=mc, asc=ang["ASC"],
                            armc=armc, cusps=tuple(cusps), obliquity=eps)


# --------------------------------------------------------------------------
# high-level reports
# --------------------------------------------------------------------------

from ..core.aspects import AspectHit, find_aspects  # noqa: E402
from ..core.chart import _house_of  # noqa: E402
from ..core.settings import AspectDef  # noqa: E402

#: tight 1-degree majors used for prog->natal and directed->natal grids
TIGHT_MAJORS: tuple[AspectDef, ...] = tuple(
    AspectDef(k, ab, ang, 1.0, 1.0, True) for k, ab, ang in [
        ("conjunction", "con", 0.0), ("sextile", "sex", 60.0),
        ("square", "squ", 90.0), ("trine", "tri", 120.0),
        ("opposition", "opp", 180.0),
    ]
)


@dataclass(frozen=True, slots=True)
class ProgressedReport:
    kind: str                       # secondary | tertiary | minor
    natal: Chart
    target_jd_ut: float
    prog_jd_ut: float
    age_years: float
    clock: str                      # e.g. "1d=1yr(tropical 365.2422d)"
    chart: Chart                    # full chart at prog jd, birth place (quotidian angles)
    angles_sa: ProgressedAngles | None
    natal_wheel_houses: dict[str, int | None]
    hits: list[AspectHit]           # prog point -> natal point/angle, 1 deg majors


def compute_progressed(
    natal_chart: Chart,
    target: Moment,
    kind: str = "secondary",
    year: str = "tropical",
    month: str = "tropical",
    eph: Ephemeris | None = None,
) -> ProgressedReport:
    natal = natal_chart.moment
    if kind == "secondary":
        pjd = secondary_jd(natal, target.jd_ut, year)
        clock = f"1d=1yr({year} {YEAR_LENGTHS[year]}d)"
    elif kind == "tertiary":
        pjd = tertiary_jd(natal, target.jd_ut, month)
        clock = f"1d=1mo({month} {MONTH_LENGTHS[month]}d)"
    elif kind == "minor":
        pjd = minor_jd(natal, target.jd_ut, month, year)
        clock = f"1mo=1yr({month} {MONTH_LENGTHS[month]}d)"
    else:
        raise ValueError(f"unknown progression kind {kind!r}")

    pm = progressed_moment(natal, pjd)
    chart = compute_chart(pm, natal_chart.settings, eph, kind=f"{kind}-progressed")

    angles_sa = None
    if kind == "secondary" and natal_chart.angles is not None:
        arc = solar_arc(natal, target.jd_ut, year, eph)
        angles_sa = progressed_angles_solar_arc_mc(natal_chart, pjd, arc)

    wheel = {k: (_house_of(chart.points[k].lon, natal_chart.cusps)
                 if natal_chart.cusps else None) for k in chart.points}

    grid_settings = natal_chart.settings.with_(aspects=TIGHT_MAJORS, angle_orb=1.0)
    prog_pos = [(f"p.{k}", chart.points[k].lon, chart.points[k].lon_speed)
                for k in chart.points]
    natal_pos = [(k, natal_chart.points[k].lon, None) for k in natal_chart.points]
    if natal_chart.angles is not None:
        natal_pos += [(a, natal_chart.angles[a], None) for a in ("ASC", "MC")]
    hits = find_aspects(prog_pos, grid_settings, pairs_with=natal_pos)

    age = (target.jd_ut - natal.jd_ut) / YEAR_LENGTHS[year]
    return ProgressedReport(kind=kind, natal=natal_chart, target_jd_ut=target.jd_ut,
                            prog_jd_ut=pjd, age_years=age, clock=clock, chart=chart,
                            angles_sa=angles_sa, natal_wheel_houses=wheel, hits=hits)


@dataclass(frozen=True, slots=True)
class SolarArcReport:
    natal: Chart
    target_jd_ut: float
    arc: float
    year: str
    directed: dict[str, float]      # points + angles + cusps, natal + arc
    hits: list[AspectHit]           # directed point -> natal point/angle


def compute_solar_arc(
    natal_chart: Chart,
    target: Moment,
    year: str = "tropical",
    eph: Ephemeris | None = None,
) -> SolarArcReport:
    natal = natal_chart.moment
    arc = solar_arc(natal, target.jd_ut, year, eph)
    directed: dict[str, float] = {
        k: norm360(p.lon + arc) for k, p in natal_chart.points.items()
    }
    if natal_chart.angles is not None:
        for a in ("ASC", "MC"):
            directed[f"{a}"] = norm360(natal_chart.angles[a] + arc)

    grid_settings = natal_chart.settings.with_(aspects=TIGHT_MAJORS, angle_orb=1.0)
    directed_pos = [(f"d.{k}", lon, None) for k, lon in directed.items()]
    natal_pos = [(k, natal_chart.points[k].lon, None) for k in natal_chart.points]
    if natal_chart.angles is not None:
        natal_pos += [(a, natal_chart.angles[a], None) for a in ("ASC", "MC")]
    hits = [h for h in find_aspects(directed_pos, grid_settings, pairs_with=natal_pos)
            if h.p1[2:] != h.p2]   # drop self-to-self (always exactly +arc)
    return SolarArcReport(natal=natal_chart, target_jd_ut=target.jd_ut, arc=arc,
                          year=year, directed=directed, hits=hits)
