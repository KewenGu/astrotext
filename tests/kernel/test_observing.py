"""K6 acceptance — kernel.observing vs SE 2.10.03 black-box fixtures.

Gates mirror tools/verify_kernel.py: stars ≤0.2″ within 1850-2150 /
≤0.8″ full-span (sefstars' Hipparcos-1997 proper motions vs our van
Leeuwen 2007 — ours ≡ Skyfield to 0.0001″ on the same rows); sun
rise/set ≤1 s (black-box-calibrated −0.61233° effective horizon).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from astrotext.kernel import bodies as kb
from astrotext.kernel import observing as ko

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "observing.json").read_text())

pytestmark = pytest.mark.skipif(
    not (kb.kernel_data_path() / "de440_1799_2400.bsp").exists(),
    reason="DE440 excerpt not fetched (tools/fetch_kernel_data.py)")


def wrap_asec(d):
    return ((d + 180.0) % 360.0 - 180.0) * 3600.0


@pytest.mark.parametrize(
    "case", FIX["stars"],
    ids=lambda c: f"{c['star'].replace(' ', '')}@{c['jd_tt']:.0f}")
def test_star_parity(case):
    a = ko.star_apparent(case["star"], case["jd_tt"])
    d = float(np.hypot(wrap_asec(a.lon - case["lon"]),
                       (a.lat - case["lat"]) * 3600.0))
    core = 2396758.5 < case["jd_tt"] < 2506332.5
    assert d <= (0.2 if core else 0.8)


@pytest.mark.parametrize(
    "case", FIX["rise_set"],
    ids=lambda c: f"{c['kind']}@{c['jd_ut']:.0f}lat{c['lat']:.0f}")
def test_rise_set_parity(case):
    t = ko.next_sun_event(case["jd_ut"], case["lat"], case["lon"],
                          case["kind"])
    assert t is not None
    assert abs(t - case["t"]) * 86400.0 <= 1.0


def test_star_catalog_complete():
    assert len(ko.STAR_NAMES) == 22
    assert "Regulus" in ko.STAR_NAMES and "Deneb Algedi" in ko.STAR_NAMES


def test_star_vectorized_matches_scalar():
    jds = np.array([2400000.5, 2451545.0, 2500000.5])
    vec = ko.star_apparent("Spica", jds)
    for i, j in enumerate(jds):
        one = ko.star_apparent("Spica", float(j))
        assert vec.lon[i] == pytest.approx(one.lon, abs=1e-12)


def test_spica_lahiri_anchor():
    """Spica sits within ~1° of 0° sidereal Libra under Lahiri (the
    zodiac's defining star, Citra paksha) — coarse sanity."""
    from astrotext.kernel import sidereal as ks
    a = ko.star_apparent("Spica", 2451545.0)
    sid = ks.sidereal_lon(a.lon, 2451545.0, "lahiri")
    assert abs(sid - 180.0) < 1.0


def test_rise_before_set_daytime_order():
    """At a temperate latitude the day sequence rise < set < next rise."""
    r = ko.next_sun_event(2451545.1, 40.0, 0.0, "rise")
    s = ko.next_sun_event(r, 40.0, 0.0, "set")
    r2 = ko.next_sun_event(s, 40.0, 0.0, "rise")
    assert r < s < r2 and 0.3 < (r2 - r) < 1.1


def test_polar_night_returns_none():
    """Tromsø-ish latitude, mid-December: no sunrise within 1.5 days."""
    assert ko.next_sun_event(2451890.0, 69.6, 18.9, "rise") is None


def test_unknown_star_raises():
    with pytest.raises(KeyError):
        ko.star_apparent("Vulcan's Forge", 2451545.0)


def test_bad_kind_raises():
    with pytest.raises(ValueError):
        ko.next_sun_event(2451545.0, 0.0, 0.0, "transit")
