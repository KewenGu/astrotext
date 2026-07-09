"""K5 acceptance — kernel.sidereal vs SE 2.10.03 black-box fixtures.

Gates mirror tools/verify_kernel.py: ayanamsa (both flavours) ≤0.01″;
end-to-end sidereal longitudes ≤0.015″ planets / ≤0.06″ Moon (the K2
lunar DE divergence rides on top).  Plus the defining-constant
round-trips against the published values (SE manual §2.8).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from astrotext.kernel import bodies as kb
from astrotext.kernel import sidereal as ks
from astrotext.kernel.frames import nutation

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "sidereal.json").read_text())


def wrap_asec(d):
    return ((d + 180.0) % 360.0 - 180.0) * 3600.0


@pytest.mark.parametrize(
    "case", FIX["ayanamsa"],
    ids=lambda c: f"{c['mode']}@{c['jd_tt']:.0f}")
def test_ayanamsa_parity(case):
    got_t = ks.ayanamsa_deg(case["jd_tt"], case["mode"], True)
    got_m = ks.ayanamsa_deg(case["jd_tt"], case["mode"], False)
    assert abs(wrap_asec(got_t - case["true"])) <= 0.01
    assert abs(wrap_asec(got_m - case["mean"])) <= 0.01


@pytest.mark.parametrize(
    "case", FIX["sidereal_lon"],
    ids=lambda c: f"{c['mode']}-{c['body']}@{c['jd_tt']:.0f}")
def test_native_sidereal_parity(case):
    a = kb.apparent(case["body"], case["jd_tt"])
    got = ks.sidereal_lon(a.lon, case["jd_tt"], case["mode"])
    gate = 0.06 if case["body"] == "moon" else 0.015
    assert abs(wrap_asec(got - case["lon"])) <= gate


def test_defining_constants_sanity():
    """a0_mean + Δψ(t0) sits near the published prose defining values
    (SE manual §2.8): Lahiri 23°15′00″.658 within 0.2″; Fagan/Bradley's
    prose value 24°02′31″.36 is itself approximate — SE's internal
    constant differs from it by 3.7″ (measured), so only a coarse bound
    applies.  The binding acceptance is the SE parity fixtures above."""
    checks = {"lahiri": (23 + 15 / 60 + 0.658 / 3600, 0.2),
              "fagan_bradley": (24 + 2 / 60 + 31.36 / 3600, 4.0)}
    for mode, (pub, tol) in checks.items():
        t0, a0 = ks.AYANAMSAS[mode]
        true_at_t0 = a0 + np.degrees(nutation(t0)[0])
        assert abs(true_at_t0 - pub) * 3600.0 <= tol


def test_flavour_difference_is_nutation():
    jds = np.linspace(2380000.0, 2597000.0, 25)
    d = (ks.ayanamsa_deg(jds, "lahiri", True)
         - ks.ayanamsa_deg(jds, "lahiri", False))
    dpsi = np.degrees(nutation(jds)[0])
    assert np.max(np.abs(d - dpsi)) * 3600.0 < 1e-9


def test_rate_is_precession():
    """Ayanamsa grows ~50.29″/yr (general precession)."""
    a = ks.ayanamsa_deg(2451545.0, "lahiri", False)
    b = ks.ayanamsa_deg(2451545.0 + 36525.0, "lahiri", False)
    assert (b - a) * 36.0 == pytest.approx(50.29, abs=0.05)


def test_sidereal_lon_wraps():
    assert ks.sidereal_lon(10.0, 2451545.0, "lahiri") == pytest.approx(
        (10.0 - ks.ayanamsa_deg(2451545.0, "lahiri")) % 360.0)


def test_unknown_mode_raises():
    with pytest.raises(KeyError):
        ks.ayanamsa_deg(2451545.0, "deluce")
