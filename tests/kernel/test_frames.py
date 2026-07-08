"""K1 — kernel.frames mathematical properties and cross-checks.

Positional parity vs swetest is exercised end-to-end at K2 (the K0 probe
already bounded the total frame gap at ≤ 0.005″); here we pin down the
mathematical invariants and the vectorization contract.
"""
from __future__ import annotations

import numpy as np
import pytest

from astrotext.kernel import frames as fr

J2000 = 2451545.0
JDS = np.array([2378497.0, 2415020.5, J2000, 2488069.5, 2597641.0])


def test_bpn_matrices_are_rotations():
    r = fr.bpn_matrix(JDS)
    ident = np.einsum("nij,nkj->nik", r, r)      # R Rᵀ
    assert np.max(np.abs(ident - np.eye(3))) < 1e-12
    assert np.linalg.det(r) == pytest.approx(1.0, abs=1e-12)


def test_bpn_at_j2000_is_near_identity():
    """At J2000 only frame bias (~23 mas) + nutation (|Δψ| ≈ 13.9″ that
    day) separate ICRS from the true equator — everything ≤ 1e-4 rad."""
    r = fr.bpn_matrix(J2000)
    off_diag = np.abs(r - np.eye(3)).max()
    assert off_diag < 1e-4
    assert r[0, 0] > 1.0 - 1e-8   # cos of a ≲14″ rotation


def test_mean_obliquity_j2000_published_value():
    """ε_A(J2000) = 84381.406″ (IAU 2006 defining value)."""
    eps = fr.mean_obliquity(J2000)
    assert np.degrees(eps) * 3600.0 == pytest.approx(84381.406, abs=1e-3)


def test_true_obliquity_within_nutation_band():
    eps_m = fr.mean_obliquity(JDS)
    eps_t = fr.true_obliquity(JDS)
    d_asec = np.abs(np.degrees(eps_t - eps_m)) * 3600.0
    assert np.all(d_asec < 9.3)   # |Δε| ≤ ~9.2″ (largest nutation term)
    assert np.any(d_asec > 0.5)


def test_ecl_matrix_composition():
    for jd in JDS:
        recl = fr.ecl_matrix(float(jd))
        manual = fr._rx(fr.true_obliquity(float(jd))) @ fr.bpn_matrix(float(jd))
        assert np.max(np.abs(recl - manual)) < 1e-15


def test_ecliptic_pole_maps_to_lat_90():
    """R1(ε) applied to the true-equator frame sends the ecliptic pole to
    z; a vector at ecliptic lat 90° must come out with lat 90°."""
    jd = 2460000.0
    f = fr.Frames.at(jd)
    # build the ICRS direction of the ecliptic-of-date north pole:
    pole_ecl = np.array([0.0, 0.0, 1.0])
    icrs = np.linalg.inv(f.recl) @ pole_ecl
    lon, lat, r = fr.vec_to_sph(f.icrs_to_ecl(icrs))
    assert lat == pytest.approx(90.0, abs=1e-9)


def test_frames_bundle_matches_functions():
    f = fr.Frames.at(JDS)
    assert np.max(np.abs(f.rbpn - fr.bpn_matrix(JDS))) == 0.0
    v = np.array([0.3, -0.4, 0.86])
    ecl = f.icrs_to_ecl(np.broadcast_to(v, (len(JDS), 3)))
    for i, jd in enumerate(JDS):
        one = fr.Frames.at(float(jd)).icrs_to_ecl(v)
        assert np.max(np.abs(ecl[i] - one)) < 1e-15


def test_vec_to_sph_ranges():
    rng = np.random.default_rng(3)
    v = rng.normal(size=(500, 3))
    lon, lat, r = fr.vec_to_sph(v)
    assert np.all((lon >= 0.0) & (lon < 360.0))
    assert np.all((lat >= -90.0) & (lat <= 90.0))
    assert np.all(r > 0)


def test_gst_j2000_published_value():
    """GMST at J2000 = 18.697374558 h; GAST differs by eq. of equinoxes
    (< 1.2 s of time)."""
    gast_h = np.degrees(fr.gst06a(J2000, J2000)) / 15.0
    assert gast_h == pytest.approx(18.697374558, abs=0.001)
