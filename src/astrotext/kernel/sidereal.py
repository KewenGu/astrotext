"""Sidereal zodiac for kernel v2 — ayanamsas (KERNEL.md §8).

SE's default (traditional) ayanamsa algorithm, pinned black-box and
matching its manual §2.8.12: an in-plane accumulation

    ayanamsa_mean(t) = a0 + p_A(t) − p_A(t0)

where p_A is the general precession in longitude.  The IAU 2006
polynomial (Capitaine, Wallace & Chapront 2003; IAU 2006 resolution)

    p_A = 5028.796195·T + 1.1054348·T² + 0.00007964·T³
          − 0.000023857·T⁴ − 0.0000000383·T⁵   [arcsec, T = TT cy from J2000]

reproduces SE 2.10.03 to ≤ 0.0019″ over 1800-2399 for all four modes
(measured; both the rigorous-3D fiducial transform and the IAE-1989
polynomial were tested and rejected at 0.05″ / 1.3″).

Flavours (measured identities, exact):

    ayanamsa_true(t) = ayanamsa_mean(t) + Δψ(t)      (nutation in lon)
    sidereal_lon     = tropical_lon(true equinox) − ayanamsa_true
                     = tropical_lon(mean equinox) − ayanamsa_mean

This is SE's native FLG_SIDEREAL semantics.  The historical trap
documented in TECHNIQUES.md — "tropical minus get_ayanamsa differs by
3-14″" — was a *flavour mix* (mean ayanamsa against true-equinox
longitudes); with matching flavours the subtraction is exact.

Defining constants: epochs are the published ones (Fagan/Bradley
1950-01-01, Lahiri 1956-03-21 0:00 TDT, Raman & Krishnamurti J1900);
the mean-flavour a0 values are black-box SE samples at t0 (§11).
Sanity anchors: a0 + Δψ(t0) lands 0.14″ from Lahiri's published
23°15′00″.658 and 3.7″ from Fagan/Bradley's prose 24°02′31″.36 — the
prose values are rounded/derived, SE's internal constants are the
operative definition (tests assert the coarse agreement; the binding
gate is full-span SE parity ≤0.003″).
"""
from __future__ import annotations

import numpy as np

from .frames import nutation

__all__ = ["AYANAMSAS", "ayanamsa_deg", "sidereal_lon"]

#: mode → (t0 jd_tt, a0_mean degrees)
AYANAMSAS: dict[str, tuple[float, float]] = {
    "fagan_bradley": (2433282.5, 24.041932764),
    "lahiri": (2435553.5, 23.245560955),
    "raman": (2415020.0, 21.014210013),
    "krishnamurti": (2415020.0, 22.363659013),
}


def _pa_deg(jd_tt):
    """General precession in longitude, IAU 2006 (degrees)."""
    t = (np.asarray(jd_tt, dtype=float) - 2451545.0) / 36525.0
    return (5028.796195 * t + 1.1054348 * t ** 2 + 0.00007964 * t ** 3
            - 0.000023857 * t ** 4 - 0.0000000383 * t ** 5) / 3600.0


def ayanamsa_deg(jd_tt, mode: str = "lahiri", true_equinox: bool = True):
    """Ayanamsa in degrees at jd (TT).  Vectorized over jd.

    ``true_equinox=True`` (default) pairs with the kernel's apparent
    (true-equinox) longitudes; ``False`` gives the mean flavour.
    """
    try:
        t0, a0 = AYANAMSAS[mode]
    except KeyError:
        raise KeyError(
            f"unknown ayanamsa {mode!r}; have {sorted(AYANAMSAS)}") from None
    ay = a0 + _pa_deg(jd_tt) - _pa_deg(t0)
    if true_equinox:
        ay = ay + np.degrees(nutation(jd_tt)[0])
    return ay if np.ndim(jd_tt) else float(ay)


def sidereal_lon(tropical_lon_deg, jd_tt, mode: str = "lahiri"):
    """Apparent (true-equinox) tropical longitude → sidereal longitude."""
    return (np.asarray(tropical_lon_deg, dtype=float)
            - ayanamsa_deg(jd_tt, mode, True)) % 360.0


def ayanamsa_speed(jd_tt, mode: str = "lahiri") -> float:
    """d(ayanamsa_true)/dt in °/day — the p_A rate plus the nutation
    rate (up to ±4e-5 °/day).  SE's sidereal speeds subtract exactly
    this from the tropical speeds (measured)."""
    h = 0.01
    j = np.asarray(jd_tt, dtype=float)
    d1 = ayanamsa_deg(j + h, mode, True) - ayanamsa_deg(j - h, mode, True)
    d2 = ayanamsa_deg(j + 2 * h, mode, True) - ayanamsa_deg(j - 2 * h,
                                                            mode, True)
    out = (8.0 * d1 - d2) / (12.0 * h)
    return float(out) if np.ndim(jd_tt) == 0 else out
