"""Timezone / calendar edge cases — the acceptance set for design axiom #3.

The Chinese historical cases matter most for this project's users:
  * China used DST 1986-1991 (+09:00 in summer)
  * Asia/Shanghai before 1901 is tzdb's LMT era (+08:05:43, Shanghai's LMT)
"""
import datetime as dt

import pytest
from astrotext.kernel import timescales as _ts

from astrotext.timespace import (
    JULIAN, Moment, NonexistentLocalTime, Place, TimezoneResolutionError,
    from_utc, lmt_offset, resolve,
)

BEIJING = Place(lat=39.9042, lon=116.4074, name="Beijing", tz="Asia/Shanghai")


def test_china_dst_summer_1988():
    m = resolve(dt.datetime(1988, 6, 15, 14, 30), BEIJING)
    assert m.utc == dt.datetime(1988, 6, 15, 5, 30, tzinfo=dt.timezone.utc)
    assert m.utc_offset == dt.timedelta(hours=9)
    assert m.flags == ()


def test_china_winter_1988():
    m = resolve(dt.datetime(1988, 1, 15, 14, 30), BEIJING)
    assert m.utc == dt.datetime(1988, 1, 15, 6, 30, tzinfo=dt.timezone.utc)
    assert m.utc_offset == dt.timedelta(hours=8)


def test_dst_gap_raises():
    with pytest.raises(NonexistentLocalTime):
        resolve(dt.datetime(1986, 5, 4, 2, 30), BEIJING)


def test_dst_ambiguity_folds():
    m0 = resolve(dt.datetime(1986, 9, 14, 1, 30), BEIJING, fold=0)
    m1 = resolve(dt.datetime(1986, 9, 14, 1, 30), BEIJING, fold=1)
    assert m0.utc.hour == 16 and m0.utc.day == 13
    assert m1.utc.hour == 17 and m1.utc.day == 13
    assert any(f.startswith("ambiguous-local-time:first") for f in m0.flags)
    assert any(f.startswith("ambiguous-local-time:second") for f in m1.flags)
    assert (m1.utc - m0.utc) == dt.timedelta(hours=1)


def test_tzdb_lmt_era_warning_1900():
    m = resolve(dt.datetime(1900, 6, 1, 12, 0), BEIJING)
    assert m.utc.strftime("%H:%M:%S") == "03:54:17"  # +08:05:43 Shanghai LMT
    assert any(f.startswith("tzdb-lmt-era") for f in m.flags)


def test_explicit_lmt_uses_birth_longitude():
    m = resolve(dt.datetime(1850, 3, 10, 12, 0), BEIJING, tz="LMT")
    # 116.4074 deg * 240 s = 27937.776 -> 27938 s = 7:45:38
    assert m.utc_offset == dt.timedelta(seconds=27938)
    assert m.utc.strftime("%H:%M:%S") == "04:14:22"
    assert m.tz_used == "LMT+07:45:38"
    assert any(f.startswith("lmt-used") for f in m.flags)


def test_fixed_offset_formats():
    p = Place(lat=0, lon=0)
    for tz, hours in [("UTC+8", 8), ("+08:00", 8), ("GMT+05:30", 5.5),
                      ("UTC-3:30", -3.5), ("-11", -11)]:
        m = resolve(dt.datetime(2020, 1, 1, 12, 0), p, tz=tz)
        assert m.utc_offset == dt.timedelta(hours=hours), tz


def test_bad_tz_rejected():
    p = Place(lat=0, lon=0)
    with pytest.raises(TimezoneResolutionError):
        resolve(dt.datetime(2020, 1, 1), p, tz="Mars/Olympus")
    with pytest.raises(TimezoneResolutionError):
        resolve(dt.datetime(2020, 1, 1), p)  # no tz anywhere
    with pytest.raises(ValueError):
        resolve(dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc), p, tz="UTC+0")


def test_j2000_jd_and_delta_t():
    m = resolve(dt.datetime(2000, 1, 1, 12, 0), Place(lat=0, lon=0, tz="UTC+0"))
    # UT1-UTC was ~0.36s at J2000; SE returns JD(UT1)
    assert abs(m.jd_ut - 2451545.0) < 1.2 / 86400
    assert 62.0 < m.delta_t_sec < 65.5
    assert abs((m.jd_tt - m.jd_ut) * 86400.0 - m.delta_t_sec) < 1e-6


def test_julian_calendar_input():
    m = resolve(dt.datetime(1500, 2, 20, 12, 0), Place(lat=51.5, lon=0.0, tz="LMT"),
                calendar=JULIAN)
    assert abs(m.jd_ut - _ts.julday(1500, 2, 20, 12.0, _ts.JULIAN)) < 1e-9
    assert "julian-calendar-input" in m.flags
    # Julian 1500-02-20 == Gregorian 1500-03-01 (10-day gap)
    assert (m.utc.month, m.utc.day) == (3, 1)
    with pytest.raises(TimezoneResolutionError):
        resolve(dt.datetime(1500, 2, 20, 12, 0), BEIJING, calendar=JULIAN)  # IANA + julian


def test_from_utc_roundtrip():
    u = dt.datetime(2026, 7, 8, 3, 0, tzinfo=dt.timezone.utc)
    m = from_utc(u, BEIJING)
    m2 = resolve(dt.datetime(2026, 7, 8, 3, 0), BEIJING, tz="UTC+0")
    assert abs(m.jd_ut - m2.jd_ut) < 1e-12
    assert m.utc == u


def test_lmt_offset_signs():
    assert lmt_offset(0.0) == dt.timedelta(0)
    assert lmt_offset(-75.0) == dt.timedelta(hours=-5)
    assert lmt_offset(180.0) == dt.timedelta(hours=12)


def test_microseconds_survive():
    m = resolve(dt.datetime(1988, 6, 15, 14, 30, 30, 500000), BEIJING)
    assert m.utc.second == 30 and m.utc.microsecond == 500000
