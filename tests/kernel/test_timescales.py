"""K1 acceptance — kernel.timescales vs SE 2.10.03 black-box fixtures.

Runs WITHOUT Swiss Ephemeris.  Truth values: tests/kernel/fixtures/
timescales.json (generator: tools/gen_kernel_fixtures.py, vendored
pyswisseph 2.10.03).

Bounds (KERNEL.md §5): ΔT parity ≤ 0.01 s on fixtures (achieved ~1e-4 s,
the grid-interpolation bound); jd parity ≤ 3e-9 day ≈ 0.26 ms.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from astrotext.kernel import timescales as ts

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "timescales.json").read_text())

DAY = 86400.0


# ---------------------------------------------------------------- ΔT parity

@pytest.mark.parametrize("case", FIX["deltat"], ids=lambda c: f"jd{c['jd_ut']}")
def test_deltat_parity_both_flavors(case):
    """Grid-interpolation bound ~1e-4 s; acceptance (KERNEL.md §5) is 0.01 s."""
    got_swi = ts.deltat_sec(case["jd_ut"], "swieph")
    got_jpl = ts.deltat_sec(case["jd_ut"], "jpleph")
    assert abs(got_swi - case["swieph_sec"]) <= 5e-4
    assert abs(got_jpl - case["jpleph_sec"]) <= 5e-4


def test_deltat_days_signature():
    c = FIX["deltat"][13]  # 2000-01-01
    assert abs(ts.deltat(c["jd_ut"]) * DAY - c["swieph_sec"]) <= 5e-4


def test_deltat_flavors_coincide_after_1955():
    jds = np.linspace(2436000.0, 2596000.0, 50)   # ~1957..2395
    d = ts.deltat_sec(jds, "swieph") - ts.deltat_sec(jds, "jpleph")
    assert np.max(np.abs(d)) <= 2e-3


def test_deltat_flavors_differ_before_1955():
    assert abs(ts.deltat_sec(2378500.0, "swieph")
               - ts.deltat_sec(2378500.0, "jpleph")) > 0.05


def test_deltat_outside_span_raises():
    with pytest.raises(ts.KernelTimeError):
        ts.deltat_sec(2300000.0)
    with pytest.raises(ts.KernelTimeError):
        ts.deltat_sec(2700000.0)


def test_deltat_vectorized_matches_scalar():
    jds = np.array([c["jd_ut"] for c in FIX["deltat"]])
    vec = ts.deltat_sec(jds)
    for j, v in zip(jds, vec):
        assert v == ts.deltat_sec(float(j))


# ------------------------------------------------------------ utc_to_jd

@pytest.mark.parametrize(
    "case", FIX["utc_to_jd"],
    ids=lambda c: "{}-{:02d}-{:02d}T{:02d}:{:02d}".format(*map(int, c["utc"][:5])))
def test_utc_to_jd_parity(case):
    y, m, d, h, mi, s = case["utc"]
    tt, ut1 = ts.utc_to_jd(int(y), int(m), int(d), int(h), int(mi), float(s))
    assert abs(tt - case["jd_tt"]) <= 3e-9, "TT drift vs SE"
    assert abs(ut1 - case["jd_ut1"]) <= 3e-9, "UT1 drift vs SE"


def test_leap_era_tt_is_exact_leap_arithmetic():
    """1972..2033 TT involves no ΔT: parity at jd float precision (one ulp
    of a modern jd is ~4.7e-10 day ≈ 40 µs)."""
    for case in FIX["utc_to_jd"]:
        y, m, d, h, mi, s = case["utc"]
        day_jd = ts.julday(int(y), int(m), int(d))
        if 2441317.5 <= day_jd <= ts.julday(2033, 7, 1):
            tt, _ = ts.utc_to_jd(int(y), int(m), int(d), int(h), int(mi),
                                 float(s))
            assert abs(tt - case["jd_tt"]) <= 6e-10


def test_tt_monotonic_through_leap_second():
    """2016-12-31 23:59:59 → :60 → 2017-01-01 00:00:00 advances by 1 s
    (to within the jd float quantum, ~40 µs)."""
    a = ts.utc_to_jd(2016, 12, 31, 23, 59, 59.0)[0]
    b = ts.utc_to_jd(2016, 12, 31, 23, 59, 60.0)[0]
    c = ts.utc_to_jd(2017, 1, 1, 0, 0, 0.0)[0]
    assert (b - a) * DAY == pytest.approx(1.0, abs=1e-4)
    assert (c - b) * DAY == pytest.approx(1.0, abs=1e-4)


def test_future_ut1_fallback_flip():
    """SE 2.10.03 abandons the frozen leap table during 2033 (implied
    UT1−UTC < −1 s) and treats civil time as UT1 from there on."""
    tt_a, ut1_a = ts.utc_to_jd(2033, 7, 1, 0, 0, 0.0)
    assert (tt_a - ts.julday(2033, 7, 1)) * DAY == pytest.approx(
        69.184, abs=5e-4)                      # still leap-UTC mode
    tt_b, ut1_b = ts.utc_to_jd(2033, 12, 31, 0, 0, 0.0)
    assert ut1_b == pytest.approx(ts.julday(2033, 12, 31), abs=1e-10)
    tt_c, ut1_c = ts.utc_to_jd(2399, 12, 31, 12, 0, 0.0)
    assert ut1_c == pytest.approx(ts.julday(2399, 12, 31, 12.0), abs=1e-10)


def test_uat_anchor_1994():
    """v1 UAT: 1994-07-29 02:30 UTC → UT1−UTC ≈ +0.74 s (astro.com-verified)."""
    tt, ut1 = ts.utc_to_jd(1994, 7, 29, 2, 30, 0.0)
    naive = ts.julday(1994, 7, 29, 2.5)
    assert (ut1 - naive) * DAY == pytest.approx(0.7402, abs=5e-4)


def test_pre1972_civil_time_is_ut1():
    tt, ut1 = ts.utc_to_jd(1950, 6, 1, 12, 0, 0.0)
    assert ut1 == pytest.approx(ts.julday(1950, 6, 1, 12.0), abs=1e-12)
    assert (tt - ut1) * DAY == pytest.approx(
        ts.deltat_sec(ut1, "jpleph"), abs=1e-4)   # jd float quantum


def test_tai_minus_utc_steps():
    assert ts.tai_minus_utc(2441317.5) == 10
    assert ts.tai_minus_utc(2457754.4) == 36
    assert ts.tai_minus_utc(2457754.5) == 37
    assert ts.tai_minus_utc(2461041.5) == 37   # 2026: still 37
    with pytest.raises(ts.KernelTimeError):
        ts.tai_minus_utc(2441317.0)


# ------------------------------------------------------------ calendars

@pytest.mark.parametrize("case", FIX["julday"],
                         ids=lambda c: f"{c['cal']}{c['date'][0]}")
def test_julday_parity(case):
    y, m, d, h = case["date"]
    cal = ts.GREGORIAN if case["cal"] == "g" else ts.JULIAN
    assert ts.julday(int(y), int(m), int(d), float(h), cal) == pytest.approx(
        case["jd"], abs=1e-9)


@pytest.mark.parametrize("case", FIX["revjul"],
                         ids=lambda c: f"{c['cal']}jd{c['jd']:.1f}")
def test_revjul_parity(case):
    cal = ts.GREGORIAN if case["cal"] == "g" else ts.JULIAN
    y, m, d, h = ts.revjul(case["jd"], cal)
    ey, em, ed, eh = case["date"]
    assert (y, m, d) == (int(ey), int(em), int(ed))
    assert h == pytest.approx(float(eh), abs=1e-6)


def test_gregorian_reform_gap():
    """1582-10-04 (Julian) + 1 day = 1582-10-15 (Gregorian)."""
    a = ts.julday(1582, 10, 4, 12.0, ts.JULIAN)
    b = ts.julday(1582, 10, 15, 12.0, ts.GREGORIAN)
    assert b - a == pytest.approx(1.0, abs=1e-12)


def test_julday_revjul_roundtrip_property():
    rng = np.random.default_rng(7)
    for _ in range(200):
        jd = float(rng.uniform(2378497.0, 2597641.0))
        for cal in (ts.GREGORIAN, ts.JULIAN):
            y, m, d, h = ts.revjul(jd, cal)
            assert ts.julday(y, m, d, h, cal) == pytest.approx(jd, abs=1e-9)


# ------------------------------------------------------------ conversions

def test_ut1_tt_roundtrip():
    rng = np.random.default_rng(11)
    jds = rng.uniform(2378500.0, 2597600.0, 100)
    for flavor in ("swieph", "jpleph"):
        back = ts.tt_to_ut1(ts.ut1_to_tt(jds, flavor), flavor)
        assert np.max(np.abs(back - jds)) <= 1e-11
