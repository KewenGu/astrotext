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
    """
    jd_tt: object
    rbpn: np.ndarray
    eps_true: object
    recl: np.ndarray

    @classmethod
    def at(cls, jd_tt) -> "Frames":
        rbpn = bpn_matrix(jd_tt)
        eps = true_obliquity(jd_tt)
        recl = _rx(eps) @ rbpn
        return cls(jd_tt=jd_tt, rbpn=rbpn, eps_true=eps, recl=recl)

    def icrs_to_equ(self, vec):
        """ICRS vector(s) → true equator/equinox of date."""
        return np.einsum("...ij,...j->...i", self.rbpn, vec)

    def icrs_to_ecl(self, vec):
        """ICRS vector(s) → ecliptic-of-date."""
        return np.einsum("...ij,...j->...i", self.recl, vec)
