"""K3 acceptance — kernel.points vs SE 2.10.03 black-box fixtures.

Truth: tests/kernel/fixtures/points.json (generator:
tools/gen_kernel_fixtures.py).  Gates mirror tools/verify_kernel.py and
its documented allowances:

* true_node ≤ 0.10″ (the osculating node amplifies the DE431→DE440
  lunar plane divergence by ~1/sin i ≈ 11; measured 0.058″ full-span);
* mean_node ≤ 0.8″, mean_apogee ≤ 2.0″ lon / 0.3″ lat — published
  Meeus/ELP-2000 polynomials + inclined-orbit projection vs SE's
  Moshier fit with DE431-derived corrections (SE manual §2.2.1 states
  ~1″ self-precision; display is 1″);
* speeds vs SE's reported values: loose (SE speed-polynomial approx).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from astrotext.kernel import bodies as kb
from astrotext.kernel import points as kp

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "points.json").read_text())
CASES = FIX["cases"]

pytestmark = pytest.mark.skipif(
    not (kb.kernel_data_path() / "de440_1799_2400.bsp").exists(),
    reason="DE440 excerpt not fetched (tools/fetch_kernel_data.py)")

GATES = {
    "true_node": dict(lon=0.10, lat=0.0, dist=2e-9, spd=1e-4),
    "mean_node": dict(lon=0.8, lat=0.0, dist=1e-9, spd=1e-5),
    "mean_apogee": dict(lon=2.0, lat=0.3, dist=1e-9, spd=1e-5),
}


def wrap_asec(d):
    return ((d + 180.0) % 360.0 - 180.0) * 3600.0


@pytest.mark.parametrize(
    "case", CASES, ids=lambda c: f"{c['body']}@{c['jd_tt']:.0f}")
def test_point_parity(case):
    g = GATES[case["body"]]
    a = kp.apparent_with_speed(case["body"], case["jd_tt"])
    assert abs(wrap_asec(a.lon - case["lon"])) <= g["lon"]
    if g["lat"] == 0.0:
        assert a.lat == 0.0 and case["lat"] == 0.0
    else:
        assert abs(a.lat - case["lat"]) * 3600.0 <= g["lat"]
    assert abs(a.dist - case["dist"]) <= g["dist"]
    assert abs(a.lon_speed - case["lon_speed"]) <= g["spd"]


def test_mean_node_is_retrograde_at_mean_rate():
    jds = np.linspace(2378600.0, 2597500.0, 40)
    a = kp.apparent_with_speed("mean_node", jds)
    assert np.all(a.lon_speed < -0.0515) and np.all(a.lon_speed > -0.0545)


def test_true_node_oscillates_about_mean():
    """Osculating node wobbles ±~1.7° around the mean node and can go
    direct, but never drifts far from it."""
    jds = np.linspace(2451545.0, 2451545.0 + 3650.0, 200)
    tn = kp.apparent("true_node", jds)
    mn = kp.apparent("mean_node", jds)
    d = np.abs((tn.lon - mn.lon + 180.0) % 360.0 - 180.0)
    assert d.max() < 2.5 and d.min() < 0.3


def test_apogee_latitude_bounded_by_inclination():
    jds = np.linspace(2378600.0, 2597500.0, 300)
    a = kp.apparent("mean_apogee", jds)
    assert np.max(np.abs(a.lat)) <= kp.MEAN_INCLINATION_DEG + 1e-9
    assert np.max(np.abs(a.lat)) > 5.0        # actually reaches the bound


def test_node_dist_within_osculating_range():
    jds = np.linspace(2378600.0, 2597500.0, 100)
    a = kp.apparent("true_node", jds)
    assert np.all(a.dist > 0.0022) and np.all(a.dist < 0.0030)


def test_vectorized_matches_scalar():
    """Scalar nutation interpolation bound: 1.3 mas (see test_bodies)."""
    jds = np.array([c["jd_tt"] for c in CASES if c["body"] == "true_node"])[:5]
    vec = kp.apparent("true_node", jds)
    for i, j in enumerate(jds):
        one = kp.apparent("true_node", float(j))
        assert vec.lon[i] == pytest.approx(one.lon, abs=2e-3 / 3600.0)
        assert vec.dist[i] == pytest.approx(one.dist, abs=1e-12)


def test_unknown_point_raises():
    with pytest.raises(KeyError):
        kp.apparent("osculating_apogee", 2451545.0)
