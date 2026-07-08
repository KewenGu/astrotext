"""Planetary days & hours (unequal hours, sunrise-to-sunrise).

Conventions (classical, cited in docs/TECHNIQUES.md):
* The planetary day runs sunrise -> next sunrise and takes the weekday of its
  sunrise (local civil date).  Day rulers: Sun=Sunday, Moon=Monday, ...
* Daylight is divided into 12 equal "day hours", night into 12 "night hours".
* The first hour of the day belongs to the day ruler; subsequent hours follow
  the Chaldean descending order Saturn-Jupiter-Mars-Sun-Venus-Mercury-Moon.
* Sunrise/sunset = apparent rise/set of the solar disc center with refraction
  (Swiss Ephemeris rise_trans defaults).
* Beyond the polar circles the sun may not rise/set for months — we then
  return polar=True and no hour (flagged upstream).
"""
from __future__ import annotations

from dataclasses import dataclass

import swisseph as swe

from ..timespace.moment import Moment

__all__ = ["PlanetaryHour", "planetary_hour", "CHALDEAN_DESC", "DAY_RULERS"]

CHALDEAN_DESC = ["SATURN", "JUPITER", "MARS", "SUN", "VENUS", "MERCURY", "MOON"]
#: weekday() -> ruler, Monday=0 (python convention)
DAY_RULERS = ["MOON", "MARS", "MERCURY", "JUPITER", "VENUS", "SATURN", "SUN"]


@dataclass(frozen=True, slots=True)
class PlanetaryHour:
    polar: bool
    day_ruler: str | None = None
    weekday: str | None = None
    hour_ruler: str | None = None
    hour_no: int | None = None          # 1..24 counted from sunrise
    is_day_hour: bool | None = None
    sunrise_jd: float | None = None
    sunset_jd: float | None = None
    next_sunrise_jd: float | None = None


def _next_event(jd_start: float, rsmi: int, geopos: tuple[float, float, float]
                ) -> float | None:
    try:
        ret, tret = swe.rise_trans(jd_start, swe.SUN, rsmi, geopos)
    except Exception:
        return None
    if ret != 0:
        return None  # circumpolar
    return tret[0]


def planetary_hour(moment: Moment) -> PlanetaryHour:
    jd = moment.jd_ut
    p = moment.place
    geo = (p.lon, p.lat, p.elevation_m)

    # last sunrise at/before jd: walk forward from jd-2d
    t = jd - 2.2
    last_rise = None
    while True:
        r = _next_event(t, swe.CALC_RISE, geo)
        if r is None:
            return PlanetaryHour(polar=True)
        if r > jd:
            next_rise = r
            break
        last_rise = r
        t = r + 1e-5
    if last_rise is None or (jd - last_rise) > 1.2:
        return PlanetaryHour(polar=True)  # no rise within a day: polar regime

    sunset = _next_event(last_rise + 1e-5, swe.CALC_SET, geo)
    if sunset is None or sunset > next_rise:
        return PlanetaryHour(polar=True)

    # local civil weekday of the sunrise
    rise_local_jd = last_rise + moment.utc_offset.total_seconds() / 86400.0
    # JD weekday: JD 2451545.0 (2000-01-01) was a Saturday; python Mon=0 => Sat=5
    wd = (int(rise_local_jd + 0.5) - 2451545 + 5) % 7
    day_ruler = DAY_RULERS[wd]
    weekday_name = ["Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday"][wd]

    if jd < sunset:
        idx = int((jd - last_rise) / ((sunset - last_rise) / 12.0))
        idx = min(idx, 11)
        hour_no, is_day = idx + 1, True
    else:
        idx = int((jd - sunset) / ((next_rise - sunset) / 12.0))
        idx = min(idx, 11)
        hour_no, is_day = idx + 13, False

    start = CHALDEAN_DESC.index(day_ruler)
    hour_ruler = CHALDEAN_DESC[(start + hour_no - 1) % 7]

    return PlanetaryHour(
        polar=False, day_ruler=day_ruler, weekday=weekday_name,
        hour_ruler=hour_ruler, hour_no=hour_no, is_day_hour=is_day,
        sunrise_jd=last_rise, sunset_jd=sunset, next_sunrise_jd=next_rise,
    )
