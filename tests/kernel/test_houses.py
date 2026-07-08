"""K4 acceptance — kernel.houses vs SE 2.10.03 black-box fixtures.

Truth: tests/kernel/fixtures/houses.json (swe_houses_armc at identical
armc/eps/lat — pure formula parity, gate 0.001″; the ARMC time chain is
fixtured from swe_houses_ex with an era-windowed gate, see
tools/verify_kernel.py for the SE-sidtime-splice attribution).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from astrotext.kernel import houses as kh
from astrotext.kernel import timescales as kts

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "houses.json").read_text())


def wrap_asec(d):
    return ((d + 180.0) % 360.0 - 180.0) * 3600.0


@pytest.mark.parametrize(
    "case", FIX["cases"],
    ids=lambda c: f"{c['system']}@lat{c['lat']}armc{c['armc']:.0f}")
def test_cusp_parity(case):
    if case.get("raises"):
        with pytest.raises(kh.PolarHousesError):
            kh.cusps(case["armc"], case["eps"], case["lat"], case["system"])
        return
    ours = kh.cusps(case["armc"], case["eps"], case["lat"], case["system"])
    for i in range(12):
        assert abs(wrap_asec(ours[i] - case["cusps"][i])) <= 1e-3
    ang = kh.angles(case["armc"], case["eps"], case["lat"])
    assert abs(wrap_asec(ang["ASC"] - case["asc"])) <= 1e-3
    mc_ref = ours[9] if case["system"] in ("R", "C") else ang["MC"]
    assert abs(wrap_asec(mc_ref - case["mc"])) <= 1e-3
    assert abs(wrap_asec(ang["VERTEX"] - case["vertex"])) <= 1e-3
    assert abs(wrap_asec(ang["EQUATORIAL_ASC"] - case["eq_asc"])) <= 1e-3


@pytest.mark.parametrize("case", FIX["armc_chain"],
                         ids=lambda c: f"jd{c['jd_ut']:.0f}")
def test_armc_time_chain(case):
    """gst06a-based ARMC vs SE's — era-windowed (SE's long-term sidtime
    splice deviates outside ~1850-2100; ours matches Skyfield ≤0.0005″)."""
    jd_tt = kts.ut1_to_tt(case["jd_ut"], "swieph")
    ours = kh.armc_deg(case["jd_ut"], jd_tt, case["lon"])
    gate = 0.02 if 2410000.0 < case["jd_ut"] < 2469807.5 else 10.0
    assert abs(wrap_asec(ours - case["armc"])) <= gate


# ------------------------------------------------------------ invariants

def test_quadrant_systems_share_angles():
    armc, eps, lat = 123.456, 23.44, 40.0
    ang = kh.angles(armc, eps, lat)
    for s in kh.SYSTEMS:
        c = kh.cusps(armc, eps, lat, s)
        if s == "W":
            continue                      # whole-sign cusp 1 ≠ ASC
        assert c[0] == pytest.approx(ang["ASC"], abs=1e-9)
        if s not in ("A", "E"):
            assert c[9] == pytest.approx(ang["MC"], abs=1e-9)


def test_opposite_cusps():
    c = kh.cusps(200.0, 23.44, -35.0, "P")
    for i in range(6):
        assert (c[i] + 180.0) % 360.0 == pytest.approx(c[i + 6], abs=1e-9)


def test_cusps_monotonic_zodiacal():
    """Cusps advance monotonically around the zodiac (non-polar lat)."""
    for s in ("P", "K", "O", "R", "C", "B"):
        c = kh.cusps(77.7, 23.44, 51.5, s)
        d = [(c[(i + 1) % 12] - c[i]) % 360.0 for i in range(12)]
        assert all(x > 0 for x in d) and sum(d) == pytest.approx(360.0)


def test_equal_and_whole():
    ang = kh.angles(300.0, 23.44, 10.0)
    ce = kh.cusps(300.0, 23.44, 10.0, "A")
    cw = kh.cusps(300.0, 23.44, 10.0, "W")
    assert ce[0] == pytest.approx(ang["ASC"], abs=1e-12)
    assert all((ce[i + 1] - ce[i]) % 360.0 == pytest.approx(30.0, abs=1e-9)
               for i in range(11))
    assert cw[0] == pytest.approx(30.0 * np.floor(ang["ASC"] / 30.0))


def test_polar_rule_placidus_koch():
    with pytest.raises(kh.PolarHousesError):
        kh.cusps(10.0, 23.44, 67.0, "P")
    with pytest.raises(kh.PolarHousesError):
        kh.cusps(10.0, 23.44, -67.0, "K")
    kh.cusps(10.0, 23.44, 66.0, "P")      # inside the circle: fine


def test_vertex_is_western():
    """Vertex must sit in the western hemisphere (altitude irrelevant)."""
    rng = np.random.default_rng(6)
    for _ in range(50):
        armc = float(rng.uniform(0, 360))
        lat = float(rng.uniform(-66, 66))
        ang = kh.angles(armc, 23.44, lat)
        # reconstruct the vertex vector and check its east-component
        lam = np.radians(ang["VERTEX"])
        eps = np.radians(23.44)
        v = np.array([np.cos(lam),
                      np.sin(lam) * np.cos(eps),
                      np.sin(lam) * np.sin(eps)])
        _, _, east = kh._frame_vectors(armc, lat)
        assert float(np.dot(v, east)) < 1e-9
