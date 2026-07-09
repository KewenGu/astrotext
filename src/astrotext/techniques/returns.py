"""Returns (M3): solar, lunar, and any-planet returns.

Definitions:
* A return is the instant the transiting body regains its NATAL ecliptic
  longitude: lon(t) == lon_natal, solved to ~0.05s.
* Location: cast for the CURRENT residence by default (standard practice);
  pass the birth place to get birthplace returns.
* "Active" return = the last crossing at or before the target moment; the
  next crossing is reported as a timestamp so the reader sees the period
  boundaries.
* Precession-corrected variant: equality is solved in the fixed J2000
  frame (FLG_J2000|FLG_NONUT), the standard "precessed return".  The chart
  itself is still rendered in of-date tropical longitudes (charts must be
  frame-consistent with everything else; only the TIMING changes).
"""
from __future__ import annotations

from dataclasses import dataclass


from ..core.chart import Chart, compute_chart, default_ephemeris
from ..core.settings import Settings
from ..ephem.engine import Ephemeris
from ..timespace.moment import Moment
from ..timespace.place import Place
from .progressions import progressed_moment
from .search import angular_roots
from .transits import MAX_DAILY_SPEED

__all__ = ["ReturnReport", "compute_return", "SYNODIC_HINT"]

#: rough cycle length (days) per body — sizing the search bracket
SYNODIC_HINT = {
    "SUN": 365.2422, "MOON": 27.3217, "MERCURY": 365.0, "VENUS": 365.0,
    "MARS": 687.0, "JUPITER": 4332.0, "SATURN": 10759.0,
}

_FIXED_FRAME = "fixed"


@dataclass(frozen=True, slots=True)
class ReturnReport:
    body: str
    natal: Chart
    natal_lon_used: float       # of-date natal lon, or J2000 natal lon if precessed
    precessed: bool
    location: Place
    active_jd: float            # last crossing <= target
    next_jd: float              # first crossing > target
    residual_deg: float         # |lon(active_jd) - target lon| — must be ~0
    chart: Chart                # full chart at active_jd, at `location`


def _return_moment(natal: Moment, jd: float, place: Place) -> Moment:
    m = progressed_moment(natal, jd)  # exact-JD Moment builder (UT labels)
    # rebind to the return location
    import dataclasses
    return dataclasses.replace(m, place=place)


def compute_return(
    natal_chart: Chart,
    target: Moment,
    body: str = "SUN",
    place: Place | None = None,
    precessed: bool = False,
    settings: Settings | None = None,
    eph: Ephemeris | None = None,
) -> ReturnReport:
    eph = eph or default_ephemeris()
    place = place or target.place
    natal_jd = natal_chart.moment.jd_ut
    if target.jd_ut < natal_jd:
        raise ValueError("return target predates birth")

    frame = _FIXED_FRAME if precessed else "of-date"
    natal_lon = eph.state(natal_jd, body, frame).lon

    cycle = SYNODIC_HINT.get(body)
    if cycle is None:
        raise ValueError(f"no synodic hint for {body}; add to SYNODIC_HINT")
    step = min(35.0, max(0.4, 15.0 / MAX_DAILY_SPEED.get(body, 1.0)))

    def lon_of(t: float) -> float:
        return eph.lon(t, body, frame)

    # bracket generously: 1.3 cycles back, 1.3 cycles forward
    t0 = max(natal_jd, target.jd_ut - 1.3 * cycle)
    t1 = target.jd_ut + 1.3 * cycle
    roots = angular_roots(lon_of, natal_lon, t0, t1, step)
    if not roots:
        raise RuntimeError(f"no {body} return found in [{t0}, {t1}]")

    past = [r for r in roots if r <= target.jd_ut]
    future = [r for r in roots if r > target.jd_ut]
    # birth itself counts as the 0th crossing for a just-born target
    active = past[-1] if past else natal_jd
    nxt = future[0] if future else roots[-1]

    from ..core.angles import angdiff
    residual = abs(angdiff(lon_of(active), natal_lon))

    rm = _return_moment(natal_chart.moment, active, place)
    chart = compute_chart(rm, settings or natal_chart.settings, eph,
                          kind=f"{body.lower()}-return")
    return ReturnReport(body=body, natal=natal_chart, natal_lon_used=natal_lon,
                        precessed=precessed, location=place, active_jd=active,
                        next_jd=nxt, residual_deg=residual, chart=chart)
