"""Reference frames for kernel v2 — BPN, obliquity, ecliptic-of-date (§4-5).

All rotations come from ERFA (IAU-endorsed SOFA re-licensing):

* ``bpn_matrix``     — frame bias + precession + nutation, IAU 2006/2000A
                       (`erfa.pnm06a`): GCRS/ICRS → true equator & equinox
                       of date.
* ``true_obliquity`` — mean obliquity IAU 2006 (`erfa.obl06`) + Δε from
                       `erfa.nut06a`.
* ``ecl_matrix``     — ICRS → ecliptic-of-date (true equinox): R1(ε) · BPN.

Swiss Ephemeris parity note (KERNEL.md §5): SE splices its own long-term
precession (Vondrák et al. 2011) onto IAU models; the K0 probe bounded the
total frame gap at ≤ 0.005″ over 1800–2399 (lat residuals, Sun/Mars/Moon),
within the 0.01″ acceptance.  Measured numbers live in the K-series
verification report.

Julian dates are passed to ERFA split as (J2000, jd − J2000) to keep the
fractional part small (standard two-part-JD precision practice).

Everything is vectorized: pass an array of jd_tt and matrices stack to
(..., 3, 3).  For root-finding loops, build one :class:`Frames` per instant
grid and reuse it across bodies (the BPN series dominate cost — §10).
"""
from __future__ import annotations

import dataclasses
import functools

import erfa
import numpy as np

_J2000 = 2451545.0


def _split(jd):
    return _J2000, np.asarray(jd, dtype=float) - _J2000


def bpn_matrix(jd_tt):
    """ICRS → true equator/equinox of date; shape (..., 3, 3)."""
    j1, j2 = _split(jd_tt)
    return erfa.pnm06a(j1, j2)


def nutation(jd_tt):
    """(Δψ, Δε) radians, IAU 2000A with 2006 adjustments (nut06a)."""
    j1, j2 = _split(jd_tt)
    return erfa.nut06a(j1, j2)


def mean_obliquity(jd_tt):
    j1, j2 = _split(jd_tt)
    return erfa.obl06(j1, j2)


def true_obliquity(jd_tt):
    """ε = ε_A(IAU 2006) + Δε(2000A); radians."""
    return mean_obliquity(jd_tt) + nutation(jd_tt)[1]


def ecl_matrix(jd_tt):
    """ICRS → ecliptic-of-date (true equinox & true obliquity)."""
    rbpn = bpn_matrix(jd_tt)
    eps = true_obliquity(jd_tt)
    return _rx(eps) @ rbpn


def _rx(angle):
    """Rotation about x by +angle (equatorial → ecliptic uses R1(+ε))."""
    a = np.asarray(angle, dtype=float)
    c, s = np.cos(a), np.sin(a)
    r = np.zeros(a.shape + (3, 3))
    r[..., 0, 0] = 1.0
    r[..., 1, 1] = c
    r[..., 1, 2] = s
    r[..., 2, 1] = -s
    r[..., 2, 2] = c
    return r


def vec_to_sph(vec):
    """Unit-agnostic cartesian → (lon_deg [0,360), lat_deg, r). Vectorized
    over leading axes; vec shape (..., 3)."""
    v = np.asarray(vec, dtype=float)
    r = np.linalg.norm(v, axis=-1)
    lon = np.degrees(np.arctan2(v[..., 1], v[..., 0])) % 360.0
    lat = np.degrees(np.arcsin(np.clip(v[..., 2] / r, -1.0, 1.0)))
    return lon, lat, r


def gst06a(jd_ut1, jd_tt):
    """Greenwich apparent sidereal time, radians (feeds ARMC at K4)."""
    u1, u2 = _split(jd_ut1)
    t1, t2 = _split(jd_tt)
    return erfa.gst06a(u1, u2, t1, t2)


@dataclasses.dataclass(frozen=True)
class Frames:
    """Per-instant frame bundle, computed once and shared across bodies.

    ``jd_tt`` may be a scalar or an array; matrices broadcast accordingly.
    The IAU-2000A nutation series (the dominant cost) is evaluated
    exactly once per instant: dψ/dε feed both the BPN matrix (via
    `erfa.pn06`) and the true obliquity.
    """
    jd_tt: object
    rbpn: np.ndarray
    eps_true: object
    recl: np.ndarray
    dpsi: object = 0.0            # nutation in longitude, radians

    @classmethod
    def at(cls, jd_tt) -> "Frames":
        j1, j2 = _split(jd_tt)
        dpsi, deps = erfa.nut06a(j1, j2)
        epsa, _rb, _rp, _rbp, _rn, rbpn = erfa.pn06(j1, j2, dpsi, deps)
        eps = epsa + deps
        recl = _rx(eps) @ rbpn
        return cls(jd_tt=jd_tt, rbpn=rbpn, eps_true=eps, recl=recl,
                   dpsi=dpsi)

    def icrs_to_equ(self, vec):
        """ICRS vector(s) → true equator/equinox of date."""
        return np.einsum("...ij,...j->...i", self.rbpn, vec)

    def icrs_to_ecl(self, vec):
        """ICRS vector(s) → ecliptic-of-date."""
        return np.einsum("...ij,...j->...i", self.recl, vec)


_NUT_GRID_STEP = 0.5      # days; see _frame_node


@functools.lru_cache(maxsize=16384)
def _frame_node(idx: int):
    """Exact Frames quantities at a 0.5-day grid node (full IAU series)."""
    jd = idx * _NUT_GRID_STEP
    f = Frames.at(np.array([jd]))
    return (f.rbpn[0], f.recl[0], float(np.atleast_1d(f.eps_true)[0]),
            float(np.atleast_1d(f.dpsi)[0]))


@functools.lru_cache(maxsize=8192)
def _frames_scalar(jd_tt: float) -> Frames:
    """Scalar Frames via linear blending between exact 0.5-day nodes.

    Error budget (documented; verified end-to-end by
    tools/verify_kernel.py): the fastest nutation term (13.66 d, 0.21″)
    bounds interpolation at f″h²/8 ≈ 1.3 mas; the frame rotates ~0.07″
    across a node gap, so blending rotation matrices linearly leaves
    them orthonormal to ~1e-14.  Used ONLY on the scalar hot path
    (root-finding); instant grids, houses (ε, GST) and every K-series
    acceptance path evaluate the full series.
    """
    g = jd_tt / _NUT_GRID_STEP
    i0 = int(np.floor(g))
    f = g - i0
    r0, e0, o0, d0 = _frame_node(i0)
    r1, e1, o1, d1 = _frame_node(i0 + 1)
    rbpn = (r0 + (r1 - r0) * f)[None, :, :]
    recl = (e0 + (e1 - e0) * f)[None, :, :]
    return Frames(jd_tt=np.array([jd_tt]), rbpn=rbpn,
                  eps_true=np.array([o0 + (o1 - o0) * f]), recl=recl,
                  dpsi=np.array([d0 + (d1 - d0) * f]))


def bundle(jd_tt) -> Frames:
    """Frames for an instant array; single-instant requests are memoized
    (root-finding and states() revisit identical jds across ~14 bodies —
    the nutation series then runs once, not 14×)."""
    j = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    if j.size == 1:
        return _frames_scalar(float(j[0]))
    return Frames.at(j)
