"""L1: the Chart — one moment, one place, one settings object, all base facts.

Everything downstream (transits, progressions, returns...) composes this.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


from ..ephem.engine import BodyState, Ephemeris
from ..ephem.points import REGISTRY
from ..timespace.moment import Moment
from .angles import angdiff, norm360
from .aspects import AspectHit, find_aspects
from .dignities import DOMICILE, DignityRecord, assess, receptions
from .settings import Settings
from .zodiac import deg_in_sign, sign_index

__all__ = ["ChartPoint", "MoonInfo", "Chart", "compute_chart", "default_ephemeris"]

_EPH: Ephemeris | None = None


def default_ephemeris() -> Ephemeris:
    global _EPH
    if _EPH is None:
        _EPH = Ephemeris()
    return _EPH


@dataclass(frozen=True, slots=True)
class ChartPoint:
    key: str
    lon: float
    lat: float
    dist_au: float
    lon_speed: float
    dec: float
    retrograde: bool
    oob: bool                  # |declination| beyond obliquity of date
    sign: int
    sign_deg: float
    house: int | None


@dataclass(frozen=True, slots=True)
class MoonInfo:
    elongation: float          # moon - sun, [0, 360)
    phase: str
    waxing: bool
    illumination: float        # 0..1, geocentric (1-cos e)/2


_PHASES = ["New", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
           "Full", "Disseminating", "Last Quarter", "Balsamic"]


def _moon_phase(elong: float) -> str:
    return _PHASES[int(norm360(elong) // 45.0) % 8]


@dataclass(frozen=True, slots=True)
class Chart:
    kind: str
    moment: Moment
    settings: Settings
    obliquity: float
    points: dict[str, ChartPoint]
    cusps: tuple[float, ...] | None
    angles: dict[str, float] | None
    house_system_used: str | None
    is_day: bool | None
    sun_altitude: float | None
    moon: MoonInfo
    lots: dict[str, float]
    aspects: list[AspectHit]
    dignities: dict[str, DignityRecord]
    receptions: list[tuple[str, str, str]]
    antiscia: list[tuple[str, str, str, float]]   # (p1, kind, p2, delta)
    dispositors: dict[str, list[str]]
    flags: tuple[str, ...]

    def point_positions(self, keys: tuple[str, ...] | None = None,
                        with_speed: bool = True
                        ) -> list[tuple[str, float, float | None]]:
        ks = keys or tuple(self.points)
        return [(k, self.points[k].lon,
                 self.points[k].lon_speed if with_speed else None) for k in ks]


def _house_of(lon: float, cusps: tuple[float, ...]) -> int:
    for i in range(12):
        c1, c2 = cusps[i], cusps[(i + 1) % 12]
        if norm360(lon - c1) < norm360(c2 - c1):
            return i + 1
    return 12  # unreachable


def _antiscion(lon: float) -> float:
    """Mirror across 0 Cancer / 0 Capricorn (solstitial axis)."""
    return norm360(180.0 - lon)


def _contra_antiscion(lon: float) -> float:
    return norm360(-lon)


def compute_chart(
    moment: Moment,
    settings: Settings | None = None,
    eph: Ephemeris | None = None,
    kind: str = "natal",
) -> Chart:
    settings = settings or Settings()
    eph = eph or default_ephemeris()
    jd = moment.jd_ut
    flags: list[str] = list(moment.flags)

    # ---- obliquity of date (for out-of-bounds) ------------------------------
    obliquity = eph.obliquity_true(jd)

    # ---- raw states ----------------------------------------------------------
    states: dict[str, BodyState] = {}
    for key in settings.points:
        p = REGISTRY[key]
        if p.se_id is not None:
            states[key] = eph.state(jd, key)
    # derived south nodes
    for key in settings.points:
        p = REGISTRY[key]
        if p.se_id is None and p.derived_from:
            base = states.get(p.derived_from) or eph.state(jd, p.derived_from)
            states[key] = BodyState(
                key=key, jd_ut=jd,
                lon=norm360(base.lon + 180.0), lat=-base.lat, dist_au=base.dist_au,
                lon_speed=base.lon_speed, lat_speed=-base.lat_speed,
                dist_speed=base.dist_speed,
                ra=norm360(base.ra + 180.0), dec=-base.dec,
                ra_speed=base.ra_speed, dec_speed=-base.dec_speed,
            )

    # ---- houses & angles -----------------------------------------------------
    cusps: tuple[float, ...] | None = None
    angles: dict[str, float] | None = None
    hsys_used: str | None = None
    if not settings.unknown_time:
        try:
            cusps, named = eph.houses(jd, moment.place.lat, moment.place.lon,
                                      settings.house_system)
            hsys_used = settings.house_system
        except Exception:
            cusps, named = eph.houses(jd, moment.place.lat, moment.place.lon,
                                      settings.polar_fallback)
            hsys_used = settings.polar_fallback
            flags.append(
                f"polar-fallback:{settings.house_system}->{settings.polar_fallback}"
                f"(lat {moment.place.lat:+.4f})"
            )
        angles = {
            "ASC": named["ASC"], "MC": named["MC"],
            "DSC": norm360(named["ASC"] + 180.0), "IC": norm360(named["MC"] + 180.0),
            "ARMC": named["ARMC"], "VERTEX": named["VERTEX"],
        }
    else:
        flags.append("unknown-birth-time:houses/angles/lots suppressed; "
                     "Moon moves ~13 deg/day — its position is a noon estimate")

    # ---- chart points --------------------------------------------------------
    points: dict[str, ChartPoint] = {}
    for key in settings.points:
        st = states[key]
        points[key] = ChartPoint(
            key=key, lon=st.lon, lat=st.lat, dist_au=st.dist_au,
            lon_speed=st.lon_speed, dec=st.dec, retrograde=st.retrograde,
            oob=abs(st.dec) > obliquity,
            sign=sign_index(st.lon), sign_deg=deg_in_sign(st.lon),
            house=_house_of(st.lon, cusps) if cusps else None,
        )

    # ---- sect ----------------------------------------------------------------
    is_day: bool | None = None
    sun_alt: float | None = None
    if angles is not None and "SUN" in points:
        sun = points["SUN"]
        # above horizon = on the MC side of the ASC-DSC ecliptic axis
        is_day = norm360(sun.lon - angles["ASC"]) > 180.0
        try:
            sun_alt = eph.true_altitude(
                jd, sun.lon, sun.lat, moment.place.lat, moment.place.lon,
                elevation_m=moment.place.elevation_m, dist_au=sun.dist_au)
            if abs(sun_alt) < 0.8:
                flags.append(f"sun-near-horizon:alt {sun_alt:+.2f} deg — "
                             f"sect may flip with small birth-time errors")
            if (sun_alt > 0.8 and not is_day) or (sun_alt < -0.8 and is_day):
                # ecliptic-axis convention vs true altitude disagree beyond slack
                flags.append("sect-convention-note:ecliptic-axis and true-altitude disagree")
        except Exception:
            sun_alt = None

    # ---- moon phase ----------------------------------------------------------
    if "MOON" in points and "SUN" in points:
        elong = norm360(points["MOON"].lon - points["SUN"].lon)
        moon = MoonInfo(elongation=elong, phase=_moon_phase(elong),
                        waxing=elong < 180.0,
                        illumination=(1.0 - math.cos(math.radians(elong))) / 2.0)
    else:
        moon = MoonInfo(0.0, "n/a", True, 0.0)

    # ---- lots (day/night formulas) -------------------------------------------
    lots: dict[str, float] = {}
    if angles is not None and is_day is not None and {"SUN", "MOON"} <= points.keys():
        asc, s, m = angles["ASC"], points["SUN"].lon, points["MOON"].lon
        lots["FORTUNE"] = norm360(asc + m - s) if is_day else norm360(asc + s - m)
        lots["SPIRIT"] = norm360(asc + s - m) if is_day else norm360(asc + m - s)

    # ---- aspects ---------------------------------------------------------------
    aspect_keys = settings.aspect_points or tuple(points)
    positions = [(k, points[k].lon, points[k].lon_speed) for k in aspect_keys]
    if angles is not None:
        positions += [(a, angles[a], None) for a in settings.angle_points]
    aspects = find_aspects(positions, settings)

    # ---- dignities, receptions, dispositors ------------------------------------
    sect_for_dign = bool(is_day) if is_day is not None else True
    if is_day is None:
        flags.append("dignities-assume-day:triplicity rulers computed as day chart")
    dignities = {}
    for k in points:
        rec = assess(k, points[k].lon, sect_for_dign)
        if rec:
            dignities[k] = rec
    recs = receptions({k: points[k].lon for k in points}, sect_for_dign)

    dispositors: dict[str, list[str]] = {}
    classical = [k for k in points if k in DOMICILE]
    for k in classical:
        chain, cur, seen = [k], k, {k}
        while True:
            ruler = DOMICILE[sign_index(points[cur].lon)] if cur in points else None
            if ruler is None or ruler not in points:
                break
            chain.append(ruler)
            if ruler in seen:
                break
            seen.add(ruler)
            cur = ruler
        dispositors[k] = chain

    # ---- antiscia ---------------------------------------------------------------
    anti: list[tuple[str, str, str, float]] = []
    pkeys = list(points)
    for i, k1 in enumerate(pkeys):
        for k2 in pkeys:
            if k1 == k2:
                continue
            d = angdiff(_antiscion(points[k1].lon), points[k2].lon)
            if abs(d) <= settings.antiscia_orb and pkeys.index(k2) > i:
                anti.append((k1, "antiscia", k2, d))
            d = angdiff(_contra_antiscion(points[k1].lon), points[k2].lon)
            if abs(d) <= settings.antiscia_orb and pkeys.index(k2) > i:
                anti.append((k1, "contra-antiscia", k2, d))

    return Chart(
        kind=kind, moment=moment, settings=settings, obliquity=obliquity,
        points=points, cusps=cusps, angles=angles, house_system_used=hsys_used,
        is_day=is_day, sun_altitude=sun_alt, moon=moon, lots=lots,
        aspects=aspects, dignities=dignities, receptions=recs,
        antiscia=anti, dispositors=dispositors, flags=tuple(flags),
    )
