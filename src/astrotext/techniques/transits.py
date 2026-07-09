"""Transits (M2): the sky now against the natal chart.

Conventions:
* The transit chart is cast for the CURRENT location (relocation, standard
  practice); transiting points are ALSO placed into the natal wheel (natal
  cusps) because that placement carries the interpretive meaning.
* Hits: transiting body aspecting a natal point/angle, major aspects,
  tight orb (default 3 deg both ways).
* For every hit we search a +-window (default 400 days) for ALL exact
  timestamps — a retrograde loop can produce up to three — so the reader
  never has to extrapolate an ephemeris.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.angles import angdiff, norm360
from ..core.chart import Chart, _house_of, compute_chart, default_ephemeris
from ..core.settings import MAJOR_ASPECTS, AspectDef, Settings
from ..ephem.engine import Ephemeris
from ..timespace.moment import Moment
from .search import angular_roots

__all__ = ["TransitHit", "TransitReport", "compute_transits", "MAX_DAILY_SPEED"]

#: conservative per-body max |longitude speed| (deg/day) for step sizing
MAX_DAILY_SPEED = {
    "SUN": 1.03, "MOON": 15.5, "MERCURY": 2.3, "VENUS": 1.3, "MARS": 0.9,
    "JUPITER": 0.3, "SATURN": 0.14, "URANUS": 0.08, "NEPTUNE": 0.05,
    "PLUTO": 0.05, "TRUE_NODE": 0.3, "MEAN_NODE": 0.06, "CHIRON": 0.16,
    "MEAN_APOGEE": 0.12, "SOUTH_NODE_TRUE": 0.3, "SOUTH_NODE_MEAN": 0.06,
}

#: transiting bodies worth reporting (nodes: north only; south is implied)
DEFAULT_TRANSITING = ("SUN", "MOON", "MERCURY", "VENUS", "MARS", "JUPITER",
                      "SATURN", "URANUS", "NEPTUNE", "PLUTO", "TRUE_NODE",
                      "CHIRON")

#: fast cycles get a shorter exact-time window (the Moon repeats monthly —
#: listing 50 timestamps would be noise, not data)
WINDOW_OVERRIDE_DAYS = {"MOON": 35.0, "SUN": 400.0, "MERCURY": 400.0,
                        "VENUS": 400.0}


@dataclass(frozen=True, slots=True)
class TransitHit:
    t_point: str
    aspect: AspectDef
    n_point: str               # natal point or angle
    n_lon: float
    separation: float
    orb_signed: float
    phase: str                 # A/S/E
    exact_jds: tuple[float, ...]   # all exact times in the search window


@dataclass(frozen=True, slots=True)
class MoonVoidInfo:
    """Void-of-course of the TRANSITING Moon (classical definition: no
    exact major aspect to the seven before it leaves its current sign)."""
    is_void: bool
    moon_sign: int
    sign_exit_jd: float
    last_exact: tuple[str, str, float] | None   # (planet, aspect-abbr, jd) before now
    next_exact: tuple[str, str, float] | None   # first after now (may be next sign)
    next_is_after_sign_change: bool


@dataclass(frozen=True, slots=True)
class TransitReport:
    natal: Chart
    sky: Chart                  # transit-moment chart at current location
    natal_wheel_houses: dict[str, int | None]
    hits: list[TransitHit]
    orb: float
    window_days: float
    moon_void: MoonVoidInfo | None = None


def _exact_times(eph: Ephemeris, key: str, natal_lon: float, theta: float,
                 t0: float, t1: float) -> tuple[float, ...]:
    step = min(35.0, max(0.4, 15.0 / MAX_DAILY_SPEED.get(key, 1.0)))

    def lon_of(t: float) -> float:
        return eph.lon(t, key)

    roots: list[float] = []
    targets = {norm360(natal_lon + theta)}
    if theta not in (0.0, 180.0):
        targets.add(norm360(natal_lon - theta))
    for tgt in sorted(targets):
        roots += angular_roots(lon_of, tgt, t0, t1, step)
    return tuple(sorted(roots))


_VOC_TARGETS = ("SUN", "MERCURY", "VENUS", "MARS", "JUPITER", "SATURN")
_VOC_ANGLES = (0.0, 60.0, 90.0, 120.0, 180.0)


def compute_moon_void(now_jd: float, eph: Ephemeris | None = None
                      ) -> MoonVoidInfo:
    """Classical (Lilly) VOC: the sky Moon perfects no major aspect to the
    seven before leaving its sign.  Aspects are solved against the MOVING
    planet (relative-longitude root), not a frozen position."""
    eph = eph or default_ephemeris()
    moon0 = eph.state(now_jd, "MOON")
    sign = int(moon0.lon // 30) % 12
    exit_lon = ((sign + 1) % 12) * 30.0
    exits = angular_roots(lambda t: eph.lon(t, "MOON"), exit_lon,
                          now_jd, now_jd + 3.2, 0.5)
    sign_exit = exits[0] if exits else now_jd + 2.7  # moon always exits < 2.7d

    events: list[tuple[float, str, str]] = []
    for pk in _VOC_TARGETS:
        def rel(t: float, _pk=pk) -> float:
            return norm360(eph.lon(t, "MOON") - eph.lon(t, _pk))
        for theta in _VOC_ANGLES:
            targets = {theta} if theta in (0.0, 180.0) else {theta, 360.0 - theta}
            for tgt in targets:
                for r in angular_roots(rel, tgt, now_jd - 3.2, now_jd + 6.5, 0.5):
                    abbr = {0.0: "con", 60.0: "sex", 90.0: "squ",
                            120.0: "tri", 180.0: "opp"}[theta]
                    events.append((r, pk, abbr))
    events.sort()
    past = [e for e in events if e[0] <= now_jd]
    future = [e for e in events if e[0] > now_jd]
    last = (past[-1][1], past[-1][2], past[-1][0]) if past else None
    nxt = (future[0][1], future[0][2], future[0][0]) if future else None
    is_void = not any(now_jd < e[0] <= sign_exit for e in events)
    return MoonVoidInfo(
        is_void=is_void, moon_sign=sign, sign_exit_jd=sign_exit,
        last_exact=last, next_exact=nxt,
        next_is_after_sign_change=bool(nxt and nxt[2] > sign_exit),
    )


def compute_transits(
    natal: Chart,
    now: Moment,
    settings: Settings | None = None,
    transiting: tuple[str, ...] = DEFAULT_TRANSITING,
    orb: float = 3.0,
    window_days: float = 400.0,
    eph: Ephemeris | None = None,
) -> TransitReport:
    eph = eph or default_ephemeris()
    sky_settings = (settings or natal.settings).with_(unknown_time=False)
    sky = compute_chart(now, sky_settings, eph, kind="transits")

    # transiting points inside the NATAL wheel
    wheel: dict[str, int | None] = {}
    for k in transiting:
        if k in sky.points:
            wheel[k] = (_house_of(sky.points[k].lon, natal.cusps)
                        if natal.cusps else None)

    # natal targets: points + angles
    targets: list[tuple[str, float]] = [(k, natal.points[k].lon) for k in natal.points]
    if natal.angles is not None:
        targets += [(a, natal.angles[a]) for a in ("ASC", "MC")]

    hits: list[TransitHit] = []
    for tk in transiting:
        if tk not in sky.points:
            continue
        w = min(window_days, WINDOW_OVERRIDE_DAYS.get(tk, window_days))
        t0, t1 = now.jd_ut - w, now.jd_ut + w
        tp = sky.points[tk]
        for nk, nlon in targets:
            signed = angdiff(tp.lon, nlon)
            u = abs(signed)
            for a in MAJOR_ASPECTS:
                off = u - a.angle
                if abs(off) > orb:
                    continue
                du = (1.0 if signed >= 0 else -1.0) * tp.lon_speed
                doff = (1.0 if u > a.angle else -1.0) * du
                phase = "E" if abs(off) < 1.0 / 60.0 else ("A" if doff < 0 else "S")
                hits.append(TransitHit(
                    t_point=tk, aspect=a, n_point=nk, n_lon=nlon,
                    separation=u, orb_signed=off, phase=phase,
                    exact_jds=_exact_times(eph, tk, nlon, a.angle, t0, t1),
                ))
    return TransitReport(natal=natal, sky=sky, natal_wheel_houses=wheel,
                         hits=hits, orb=orb, window_days=window_days,
                         moon_void=compute_moon_void(now.jd_ut, eph))
