"""Civil time -> UTC -> Julian Day resolution.

This is the highest-risk layer of the whole engine (design axiom #3: chart
errors come from timezones, not astronomy), so its behavior is explicit:

* IANA zones via ``zoneinfo`` (historical rules included; e.g. China's
  1986-1991 DST is handled by the system tzdb — verified in tests).
* Times that DO NOT EXIST locally (spring-forward gap) raise
  :class:`NonexistentLocalTime` — silently shifting a birth time is worse
  than failing loudly.
* AMBIGUOUS times (fall-back hour) resolve to the *first* occurrence by
  default and set a warning flag; callers may pick ``fold=1``.
* ``tz="LMT"`` uses local mean time from the birth longitude (4 min/degree),
  the standard astrological practice for births before zone time.
* If an IANA zone resolves to its pre-standardization LMT era (tzdb reports
  tzname "LMT" for the reference city), a warning flag suggests using true
  local LMT of the birthplace instead.
* Julian-calendar input is supported for pre-Gregorian dates; the JD is then
  built with Swiss Ephemeris' Julian-calendar conversion (no datetime
  arithmetic across calendars).

Julian days: ``kernel.timescales.utc_to_jd`` converts UTC -> (JD_TT, JD_UT1)
(swe_utc_to_jd parity <=0.21 ms, K1) including the
leap-second table and the Swiss Ephemeris delta-T model — the same model the
swetest reference CLI and astro.com use.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from ..kernel import timescales as _ts

from .place import Place

__all__ = [
    "GREGORIAN", "JULIAN",
    "NonexistentLocalTime", "TimezoneResolutionError",
    "Moment", "resolve",
]

GREGORIAN = "gregorian"
JULIAN = "julian"

_UTC = dt.timezone.utc


class TimezoneResolutionError(ValueError):
    """The tz string could not be understood."""


class NonexistentLocalTime(ValueError):
    """The civil time falls into a DST spring-forward gap."""


_FIXED_TZ_RE = re.compile(
    r"^(?:UTC?|GMT)?\s*([+-])\s*(\d{1,2})(?::?([0-5]\d))?(?::?([0-5]\d))?$"
)


def _fixed_offset(tz: str) -> dt.timedelta | None:
    m = _FIXED_TZ_RE.match(tz.strip())
    if not m:
        return None
    sign = 1 if m.group(1) == "+" else -1
    h, mi, s = int(m.group(2)), int(m.group(3) or 0), int(m.group(4) or 0)
    if h > 18:
        raise TimezoneResolutionError(f"fixed offset too large: {tz!r}")
    return sign * dt.timedelta(hours=h, minutes=mi, seconds=s)


def _fmt_offset(delta: dt.timedelta) -> str:
    total = round(delta.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    h, rem = divmod(total, 3600)
    mi, s = divmod(rem, 60)
    return f"{sign}{h:02d}:{mi:02d}:{s:02d}"


def lmt_offset(lon: float) -> dt.timedelta:
    """Local mean time offset for a longitude: 4 minutes per degree east."""
    return dt.timedelta(seconds=round(lon * 240.0))


@dataclass(frozen=True, slots=True)
class Moment:
    """A fully resolved instant.

    local      the civil ("wall clock") time exactly as supplied, naive
    place      where the clock was read
    calendar   'gregorian' or 'julian' (labeling of `local`)
    tz_used    what actually converted local->UTC, e.g. "Asia/Shanghai",
               "LMT+07:45:36", "UTC+08:00:00"
    utc_offset the offset that was applied (timedelta)
    utc        aware UTC datetime (for Julian-calendar input this is the
               Gregorian relabeling, derived from the JD)
    jd_ut      Julian Day (UT1) — Swiss Ephemeris time argument
    jd_tt      Julian Day (TT), includes delta-T
    delta_t_sec  TT - UT1 in seconds at this instant
    flags      deterministic tuple of warning strings, may be empty
    """

    local: dt.datetime
    place: Place
    calendar: str
    tz_used: str
    utc_offset: dt.timedelta
    utc: dt.datetime
    jd_ut: float
    jd_tt: float
    delta_t_sec: float
    flags: tuple[str, ...] = field(default=())

    def describe(self) -> str:
        return (
            f"local {self.local.isoformat(sep=' ')} [{self.calendar}] "
            f"@ {self.place.label()} | tz {self.tz_used} (UTC{_fmt_offset(self.utc_offset)}) "
            f"| UTC {self.utc.isoformat(sep=' ')} | JD(UT) {self.jd_ut:.8f} "
            f"| dT {self.delta_t_sec:+.2f}s"
        )


def _utc_to_jds(utc: dt.datetime) -> tuple[float, float, float]:
    """UTC (aware) -> (jd_ut1, jd_tt, delta_t_seconds) via Swiss Ephemeris."""
    u = utc.astimezone(_UTC)
    sec = u.second + u.microsecond / 1e6
    jd_tt, jd_ut1 = _ts.utc_to_jd(u.year, u.month, u.day, u.hour, u.minute,
                                  sec)
    return jd_ut1, jd_tt, (jd_tt - jd_ut1) * 86400.0


def resolve(
    local: dt.datetime,
    place: Place,
    tz: str | None = None,
    calendar: str = GREGORIAN,
    fold: int = 0,
) -> Moment:
    """Resolve a naive civil datetime at a place into a :class:`Moment`.

    ``tz`` overrides ``place.tz``.  ``fold`` picks the occurrence for
    ambiguous (fall-back) times: 0 = first (default), 1 = second.
    """
    if local.tzinfo is not None:
        raise ValueError("pass a NAIVE local datetime; tz comes from `tz`/`place.tz`")
    if calendar not in (GREGORIAN, JULIAN):
        raise ValueError(f"calendar must be '{GREGORIAN}' or '{JULIAN}'")

    tzspec = tz if tz is not None else place.tz
    if tzspec is None:
        raise TimezoneResolutionError(
            "no timezone: set place.tz or pass tz= (IANA name, 'LMT', or 'UTC+HH:MM')"
        )

    flags: list[str] = []

    # ---- Julian-calendar input: LMT/fixed offsets only, JD built directly --
    if calendar == JULIAN:
        return _resolve_julian(local, place, tzspec, flags)

    # ---- resolve the offset -------------------------------------------------
    if tzspec.upper() == "LMT":
        offset = lmt_offset(place.lon)
        tz_used = f"LMT{_fmt_offset(offset)}"
        flags.append(f"lmt-used:{_fmt_offset(offset)}(lon {place.lon:+.4f})")
        utc = (local - offset).replace(tzinfo=_UTC)
    else:
        fixed = _fixed_offset(tzspec)
        if fixed is not None:
            offset = fixed
            tz_used = f"UTC{_fmt_offset(offset)}"
            utc = (local - offset).replace(tzinfo=_UTC)
        else:
            try:
                zone = ZoneInfo(tzspec)
            except Exception as exc:
                raise TimezoneResolutionError(
                    f"unknown timezone {tzspec!r} (expected IANA name, 'LMT', or 'UTC+HH:MM')"
                ) from exc
            d0 = local.replace(tzinfo=zone, fold=0)
            d1 = local.replace(tzinfo=zone, fold=1)
            off0, off1 = d0.utcoffset(), d1.utcoffset()
            assert off0 is not None and off1 is not None
            if off1 > off0:
                # spring-forward gap: this wall time never happened
                raise NonexistentLocalTime(
                    f"{local.isoformat(sep=' ')} does not exist in {tzspec} "
                    f"(DST gap: clocks jumped {_fmt_offset(off0)} -> {_fmt_offset(off1)}); "
                    f"check the birth record or pass an explicit 'UTC+HH:MM' offset"
                )
            if off0 != off1:
                which = "first" if fold == 0 else "second"
                flags.append(
                    f"ambiguous-local-time:{which}-occurrence-used"
                    f"(fold={fold}; offsets {_fmt_offset(off0)}/{_fmt_offset(off1)})"
                )
            chosen = d0 if fold == 0 else d1
            offset = chosen.utcoffset() or dt.timedelta(0)
            tzname = chosen.tzname() or tzspec
            if tzname == "LMT":
                flags.append(
                    f"tzdb-lmt-era:{tzspec} predates zone time here "
                    f"({_fmt_offset(offset)} is the zone city's LMT, not the birthplace's); "
                    f"consider tz='LMT'"
                )
            tz_used = tzspec
            utc = chosen.astimezone(_UTC)

    jd_ut, jd_tt, delta_t = _utc_to_jds(utc)
    return Moment(
        local=local, place=place, calendar=GREGORIAN, tz_used=tz_used,
        utc_offset=offset, utc=utc, jd_ut=jd_ut, jd_tt=jd_tt,
        delta_t_sec=delta_t, flags=tuple(flags),
    )


def _resolve_julian(local: dt.datetime, place: Place, tzspec: str,
                    flags: list[str]) -> Moment:
    """Julian-calendar civil date. Only LMT / fixed offsets are meaningful."""
    if tzspec.upper() == "LMT":
        offset = lmt_offset(place.lon)
        tz_used = f"LMT{_fmt_offset(offset)}"
    else:
        fixed = _fixed_offset(tzspec)
        if fixed is None:
            raise TimezoneResolutionError(
                "Julian-calendar input needs tz='LMT' or a fixed 'UTC+HH:MM' offset; "
                f"IANA zones ({tzspec!r}) are meaningless before the Gregorian reform"
            )
        offset = fixed
        tz_used = f"UTC{_fmt_offset(offset)}"
    flags.append("julian-calendar-input")

    hours_local = local.hour + local.minute / 60.0 + (local.second + local.microsecond / 1e6) / 3600.0
    jd_local = _ts.julday(local.year, local.month, local.day, hours_local,
                          _ts.JULIAN)
    jd_ut = jd_local - offset.total_seconds() / 86400.0
    delta_t_days = _ts.deltat(jd_ut)
    jd_tt = jd_ut + delta_t_days

    # Gregorian relabeling of the instant, for display only.
    y, mo, d, h = _ts.revjul(jd_ut, _ts.GREGORIAN)
    hh = int(h); mm = int((h - hh) * 60); ss = (h - hh) * 3600 - mm * 60
    micro = min(999999, max(0, round((ss - int(ss)) * 1e6)))
    utc = dt.datetime(y, mo, d, hh, mm, int(ss), micro, tzinfo=_UTC)

    return Moment(
        local=local, place=place, calendar=JULIAN, tz_used=tz_used,
        utc_offset=offset, utc=utc, jd_ut=jd_ut, jd_tt=jd_tt,
        delta_t_sec=delta_t_days * 86400.0, flags=tuple(flags),
    )


def from_utc(utc: dt.datetime, place: Place) -> Moment:
    """Build a Moment from an aware UTC (or any aware) datetime — e.g. 'now'
    for transits."""
    if utc.tzinfo is None:
        raise ValueError("from_utc needs an AWARE datetime")
    u = utc.astimezone(_UTC)
    jd_ut, jd_tt, delta_t = _utc_to_jds(u)
    return Moment(
        local=u.replace(tzinfo=None), place=place, calendar=GREGORIAN,
        tz_used="UTC", utc_offset=dt.timedelta(0), utc=u,
        jd_ut=jd_ut, jd_tt=jd_tt, delta_t_sec=delta_t, flags=(),
    )
