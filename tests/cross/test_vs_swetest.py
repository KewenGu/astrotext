"""Cross-verification: the Python engine must agree with the swetest reference
CLI to print precision (7 decimals => 2e-7 deg tolerance) for every point,
every sampled instant, and every house cusp.  A failure here means our wrapper
or time handling is wrong — not a matter of opinion."""
import random

import pytest
swe = __import__("pytest").importorskip(
    "swisseph", reason="swiss backend not available (dev profile)")

from astrotext.core.angles import angdiff
from astrotext.ephem import SE_POINTS
from astrotext.verify import swetest_ref

pytestmark = pytest.mark.cross

TOL = 2e-7

FIXED_JDS = [
    2451545.0,                       # J2000
    swe.julday(1900, 6, 15, 6.5),
    swe.julday(2100, 1, 1, 18.0),
    swe.julday(1800, 1, 5, 0.25),    # near lower data-file edge
    swe.julday(2399, 12, 25, 23.5),  # near upper data-file edge
]
RANDOM_JDS = [random.Random(777).uniform(swe.julday(1800, 1, 5, 0),
                                         swe.julday(2399, 12, 25, 0))
              for _ in range(12)]


@pytest.mark.parametrize("jd", FIXED_JDS + RANDOM_JDS)
def test_positions_match_swetest(eph, jd):
    ref = swetest_ref.positions(jd)
    assert set(ref) == set(k for k in SE_POINTS)
    for key, (rlon, rlat, rspeed) in ref.items():
        st = eph.state(jd, key)
        assert abs(angdiff(st.lon, rlon)) <= TOL, (key, jd, st.lon, rlon)
        assert abs(st.lat - rlat) <= TOL, (key, jd, st.lat, rlat)
        assert abs(st.lon_speed - rspeed) <= TOL, (key, jd, st.lon_speed, rspeed)


@pytest.mark.parametrize("jd", FIXED_JDS[:3])
@pytest.mark.parametrize("loc", [(39.9042, 116.4074), (64.1466, -21.9426),
                                 (-33.8688, 151.2093)])
@pytest.mark.parametrize("hsys", ["P", "W"])
def test_houses_match_swetest(eph, jd, loc, hsys):
    lat, lon = loc
    rcusps, rnamed = swetest_ref.houses(jd, lon, lat, hsys)
    cusps, named = eph.houses(jd, lat, lon, hsys)
    for a, b in zip(cusps, rcusps):
        assert abs(angdiff(a, b)) <= TOL, (jd, loc, hsys)
    for k in ("ASC", "MC", "ARMC", "VERTEX"):
        assert abs(angdiff(named[k], rnamed[k])) <= TOL, (k, jd, loc, hsys)


def test_declination_consistency(eph):
    """Equatorial call sanity: Sun's declination at J2000 ~ -23.03 deg
    (early January) and obliquity bounds hold across samples."""
    st = eph.state(2451545.0, "SUN")
    assert -23.5 < st.dec < -22.5
    for jd in RANDOM_JDS[:6]:
        s = eph.state(jd, "SUN")
        assert abs(s.dec) < 23.5  # Sun never exceeds obliquity (lat~0)
        m = eph.state(jd, "MOON")
        assert abs(m.dec) < 29.0  # Moon max ~28.7 deg at major standstill


def test_retrograde_flag_matches_speed_sign(eph):
    for jd in RANDOM_JDS:
        for key in ("MERCURY", "VENUS", "MARS", "SATURN"):
            st = eph.state(jd, key)
            assert st.retrograde == (st.lon_speed < 0)
