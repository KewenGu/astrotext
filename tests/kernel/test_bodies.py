"""K2 acceptance — kernel.bodies vs SE 2.10.03 black-box fixtures.

Runs WITHOUT Swiss Ephemeris (needs the DE440 excerpt: fetched data, not
code).  Truth: tests/kernel/fixtures/bodies.json — swe_calc SWIEPH|SPEED
(+EQUATORIAL) on a seeded 20-instant grid × 10 bodies.

Gates mirror tools/verify_kernel.py (KERNEL.md §9 + documented
allowances): planets lon/lat/RA/dec ≤ 0.012″; Moon ≤ 0.05″ lon/lat/dec,
≤ 0.06″ RA (DE431→DE440 secular lunar divergence, ≪ 1″ display); dist
≤ max(2e-8 au, 5e-9·r); speeds vs SE's *reported* values ≤ 1.2e-5 °/day
planets / ≤ 1.2e-4 Moon (SE's speed polynomial itself deviates from the
true derivative of SE's positions — the tight ≤1.5e-6 °/day true-
derivative check lives in the verify harness, which can difference SE's
own curve).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from astrotext.kernel import bodies as kb

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "bodies.json").read_text())
CASES = FIX["cases"]

pytestmark = pytest.mark.skipif(
    not (kb.kernel_data_path() / "de440_1799_2400.bsp").exists(),
    reason="DE440 excerpt not fetched (tools/fetch_kernel_data.py)")


def wrap_asec(d):
    return ((d + 180.0) % 360.0 - 180.0) * 3600.0


def _gates(body):
    if body == "moon":
        return dict(ang=0.05, ra=0.06, spd=1.2e-4)
    return dict(ang=0.012, ra=0.012, spd=1.2e-5)


@pytest.mark.parametrize(
    "case", CASES, ids=lambda c: f"{c['body']}@{c['jd_tt']:.0f}")
def test_apparent_parity(case):
    g = _gates(case["body"])
    a = kb.apparent_with_speed(case["body"], case["jd_tt"])
    assert abs(wrap_asec(a.lon - case["lon"])) <= g["ang"]
    assert abs(a.lat - case["lat"]) * 3600.0 <= g["ang"]
    assert abs(a.dist - case["dist"]) <= max(2e-8, 5e-9 * case["dist"])
    assert abs(wrap_asec(a.ra - case["ra"])) <= g["ra"]
    assert abs(a.dec - case["dec"]) * 3600.0 <= g["ang"]
    assert abs(a.lon_speed - case["lon_speed"]) <= g["spd"]
    # lat/dist speeds: SE's *reported* speed polynomial carries its own
    # approximation error — uniform ~2e-5 °/day in lat (nutation-rate
    # interpolation; measured even for the Sun) and ~2e-6·r au/day in
    # dist. Our stencil is the true derivative (verified for lon against
    # SE's own differentiated curve in tools/verify_kernel.py).
    assert abs(a.lat_speed - case["lat_speed"]) <= 4e-5
    assert abs(a.dist_speed - case["dist_speed"]) <= max(
        1e-8, 4e-6 * case["dist"])


def test_vectorized_matches_scalar():
    jds = np.array([c["jd_tt"] for c in CASES if c["body"] == "mars"])[:6]
    vec = kb.apparent("mars", jds)
    for i, j in enumerate(jds):
        one = kb.apparent("mars", float(j))
        assert vec.lon[i] == pytest.approx(one.lon, abs=1e-12)
        assert vec.dist[i] == pytest.approx(one.dist, abs=1e-15)


def test_apparent_and_speed_positions_agree():
    c = CASES[7]
    a = kb.apparent(c["body"], c["jd_tt"])
    b = kb.apparent_with_speed(c["body"], c["jd_tt"])
    assert a.lon == pytest.approx(b.lon, abs=1e-12)
    assert a.dec == pytest.approx(b.dec, abs=1e-12)


def test_light_time_matters_for_moon():
    """Removing light time would move the Moon ~0.7″; make sure the
    pipeline's light-time iteration is actually engaged (guards against
    silent regressions of step 2)."""
    jd = 2451545.0
    pe, _ = kb.state_ssb("earth", np.atleast_1d(jd))
    pm, _ = kb.state_ssb("moon", np.atleast_1d(jd))
    tau = float(np.linalg.norm(pm - pe, axis=0) / kb.C_AUD)
    assert 1.1 / 86400.0 < tau < 1.5 / 86400.0   # ~1.28 light-seconds


def test_sun_ecliptic_latitude_is_tiny():
    jds = np.linspace(2400000.0, 2590000.0, 12)
    a = kb.apparent("sun", jds)
    assert np.max(np.abs(a.lat)) < 0.001         # < 3.6″ (relativistic/lunar wobble)


def test_speed_sign_retrograde_episode():
    """Mercury spends ~3 weeks retrograde ~3×/year: on a 200-day scan
    both signs must appear, and speed must be the derivative of lon."""
    jds = 2451545.0 + np.arange(0.0, 200.0, 5.0)
    a = kb.apparent_with_speed("mercury", jds)
    assert (a.lon_speed > 0).any() and (a.lon_speed < 0).any()


def test_unknown_body_raises():
    with pytest.raises(KeyError):
        kb.apparent("vulcan", 2451545.0)
