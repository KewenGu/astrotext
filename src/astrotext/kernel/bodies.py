"""Planetary pipeline for kernel v2 — apparent geocentric positions (§4).

Reduction chain per body at TT instant t (matching SE's default
``FLG_SWIEPH | FLG_SPEED`` semantics):

1. barycentric ICRF states from the DE440 excerpt (jplephem);
   Earth = EMB + EMB→Earth segment; Moon via the geocentric segment;
   Mars..Pluto are system barycenters — exactly what DE440 provides and
   what SE uses.
2. light time: two fixed-point iterations antedating the body while the
   observer (geocenter) stays at t.  Applied to the Moon as well
   (its 1.3 s moves lon ~0.7″).
3. gravitational light deflection by the Sun (`erfa.ld`, finite-distance
   source direction; skipped for the Sun itself).
4. annual aberration, relativistic (`erfa.ab`).
5. frame bias + precession + nutation IAU 2006/2000A (shared
   :class:`~astrotext.kernel.frames.Frames`) → true equator/equinox of
   date → RA/dec.
6. ecliptic of date with true obliquity → lon/lat.
   Distance = light-time-corrected geometric distance (SE convention).
7. speeds (dlon, dlat, ddist per day): five-point central difference of
   the full pipeline at ±h, ±2h (h = 0.01 day): truncation ~f⁗h⁴/30,
   ≲1e-9 °/day even for Mercury near perihelion — under the 1e-6 °/day
   gate (a plain 2-point stencil leaves ~8e-6 °/day there, measured).

Time argument: the SPK is evaluated at jd(TT) directly; |TDB−TT| ≤ 1.7 ms
moves even the Moon ≤ 1 mas, and K2 grid verification (tools/
verify_kernel.py) confirms parity within the gates without the term.

All entry points are vectorized over instants; pass a shared ``Frames``
when evaluating several bodies at one instant grid (§10 perf budget).
"""
from __future__ import annotations

import dataclasses
import functools

import erfa
import numpy as np
from jplephem.spk import SPK

from ..config import kernel_data_path
from .frames import Frames, vec_to_sph

AU_KM = 149597870.7                    # IAU 2012 Resolution B2
C_AUD = 299792.458 * 86400.0 / AU_KM   # speed of light, au/day
_SPEED_H = 0.01                        # day; five-point stencil step

#: engine body name → SPK chain spec ("chiron" comes from the fitted
#: Horizons Chebyshev file, tools/fetch_chiron.py — see §6)
BODIES = ("sun", "moon", "mercury", "venus", "mars", "jupiter",
          "saturn", "uranus", "neptune", "pluto", "chiron")


class KernelEphemerisError(RuntimeError):
    pass


@functools.lru_cache(maxsize=1)
def _kernel() -> SPK:
    path = kernel_data_path() / "de440_1799_2400.bsp"
    try:
        return SPK.open(path)
    except OSError as exc:
        raise KernelEphemerisError(
            f"DE440 excerpt missing: {path} — run tools/fetch_kernel_data.py"
        ) from exc


@functools.lru_cache(maxsize=1)
def _segments():
    k = _kernel()
    return {
        "ssb": {n: k[0, n] for n in range(1, 11)},
        "emb_earth": k[3, 399],
        "emb_moon": k[3, 301],
        "mer": k[1, 199],
        "ven": k[2, 299],
    }


@functools.lru_cache(maxsize=1)
def _chiron():
    path = kernel_data_path() / "chiron_horizons.npz"
    try:
        z = np.load(path)
    except OSError as exc:
        raise KernelEphemerisError(
            f"Chiron ephemeris missing: {path} — run tools/fetch_chiron.py"
        ) from exc
    return float(z["jd0"]), float(z["seg_days"]), z["coeffs"]


def _chiron_state(jd):
    """Barycentric ICRF Chiron state from the fitted Chebyshev segments;
    velocity from the analytic derivative.  jd: (n,) -> (3, n), (3, n)."""
    jd0, seg, coeffs = _chiron()
    j = np.asarray(jd, dtype=float)
    k = np.clip(((j - jd0) // seg).astype(int), 0, len(coeffs) - 1)
    x = 2.0 * (j - (jd0 + k * seg)) / seg - 1.0
    pos = np.empty((3, len(j)))
    vel = np.empty((3, len(j)))
    scale = 2.0 / seg                       # dx/djd
    for ki in np.unique(k):
        m = k == ki
        for c in range(3):
            cf = coeffs[ki, c]
            pos[c, m] = np.polynomial.chebyshev.chebval(x[m], cf)
            vel[c, m] = np.polynomial.chebyshev.chebval(
                x[m], np.polynomial.chebyshev.chebder(cf)) * scale
    return pos, vel


def _seg_state(seg, jd):
    p, v = seg.compute_and_differentiate(jd)
    return p / AU_KM, v / AU_KM        # au, au/day


def state_ssb(body: str, jd):
    """Barycentric ICRF (position, velocity) in au, au/day. Vectorized:
    jd may be scalar or (n,); arrays come back as (3,) / (3, n)."""
    s = _segments()
    if body == "earth":
        p1, v1 = _seg_state(s["ssb"][3], jd)
        p2, v2 = _seg_state(s["emb_earth"], jd)
        return p1 + p2, v1 + v2
    if body == "moon":
        p1, v1 = _seg_state(s["ssb"][3], jd)
        p2, v2 = _seg_state(s["emb_moon"], jd)
        return p1 + p2, v1 + v2
    if body == "sun":
        return _seg_state(s["ssb"][10], jd)
    if body == "chiron":
        return _chiron_state(jd)
    if body == "mercury":
        p1, v1 = _seg_state(s["ssb"][1], jd)
        p2, v2 = _seg_state(s["mer"], jd)
        return p1 + p2, v1 + v2
    if body == "venus":
        p1, v1 = _seg_state(s["ssb"][2], jd)
        p2, v2 = _seg_state(s["ven"], jd)
        return p1 + p2, v1 + v2
    idx = {"mars": 4, "jupiter": 5, "saturn": 6, "uranus": 7,
           "neptune": 8, "pluto": 9}[body]
    return _seg_state(s["ssb"][idx], jd)


@dataclasses.dataclass(frozen=True)
class Apparent:
    """Apparent geocentric coordinates (degrees, au). Scalar or arrays."""
    lon: object          # ecliptic-of-date longitude, [0, 360)
    lat: object          # ecliptic-of-date latitude
    dist: object         # light-time-corrected geometric distance
    ra: object           # true equator/equinox of date, [0, 360)
    dec: object


def apparent(body: str, jd_tt, frames: Frames | None = None) -> Apparent:
    """Full §4 reduction at jd_tt (scalar or (n,) array)."""
    jd = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    if frames is None:
        frames = Frames.at(jd)
    pe, ve = state_ssb("earth", jd)                    # (3, n)
    pb, _ = state_ssb(body, jd)
    tau = np.linalg.norm(pb - pe, axis=0) / C_AUD
    for _ in range(2):
        pb, _ = state_ssb(body, jd - tau)
        tau = np.linalg.norm(pb - pe, axis=0) / C_AUD
    p = pb - pe
    dist = np.linalg.norm(p, axis=0)
    u = (p / dist).T                                   # (n, 3) unit
    ps, _ = state_ssb("sun", jd)
    eh = (pe - ps).T
    em = np.linalg.norm(eh, axis=1)
    if body != "sun":
        q = (pb - ps).T
        q = q / np.linalg.norm(q, axis=1)[:, None]
        u = erfa.ld(1.0, u, q, eh / em[:, None], em, 1e-9)
    v = (ve / C_AUD).T
    bm1 = np.sqrt(1.0 - np.sum(v * v, axis=1))
    u = erfa.ab(u, v, em, bm1)
    u_equ = np.einsum("...ij,...j->...i", frames.rbpn, u)
    ra, dec, _ = vec_to_sph(u_equ)
    u_ecl = np.einsum("...ij,...j->...i", frames.recl, u)
    lon, lat, _ = vec_to_sph(u_ecl)

    def _out(x):
        return float(x[0]) if np.isscalar(jd_tt) or np.ndim(jd_tt) == 0 else x

    return Apparent(lon=_out(lon), lat=_out(lat), dist=_out(dist),
                    ra=_out(ra), dec=_out(dec))


@dataclasses.dataclass(frozen=True)
class ApparentSpeed(Apparent):
    lon_speed: object    # °/day (ecliptic lon; negative = retrograde)
    lat_speed: object    # °/day
    dist_speed: object   # au/day


def _wrap_diff(a, b):
    """(a − b) with longitude wrap, in degrees."""
    return (np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0


def apparent_with_speed(body: str, jd_tt) -> ApparentSpeed:
    """§4 step 7: light-time-consistent speeds, five-point stencil.

    f'(t) = [8(f(t+h) − f(t−h)) − (f(t+2h) − f(t−2h))] / 12h, with
    longitude differences taken wrap-safe.  One Frames per sample
    instant (shared across bodies only when the caller batches
    instants — the dossier path batches, root-finding refines).
    """
    jd = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    now = apparent(body, jd)
    m1 = apparent(body, jd - _SPEED_H)
    p1 = apparent(body, jd + _SPEED_H)
    m2 = apparent(body, jd - 2.0 * _SPEED_H)
    p2 = apparent(body, jd + 2.0 * _SPEED_H)
    den = 12.0 * _SPEED_H

    def _five(f_p1, f_m1, f_p2, f_m2, wrap):
        d1 = _wrap_diff(f_p1, f_m1) if wrap else np.asarray(f_p1) - f_m1
        d2 = _wrap_diff(f_p2, f_m2) if wrap else np.asarray(f_p2) - f_m2
        return (8.0 * d1 - d2) / den

    lon_s = _five(p1.lon, m1.lon, p2.lon, m2.lon, True)
    lat_s = _five(p1.lat, m1.lat, p2.lat, m2.lat, False)
    dist_s = _five(p1.dist, m1.dist, p2.dist, m2.dist, False)

    def _out(x):
        x = np.atleast_1d(x)
        return float(x[0]) if np.isscalar(jd_tt) or np.ndim(jd_tt) == 0 else x

    return ApparentSpeed(
        lon=_out(now.lon), lat=_out(now.lat), dist=_out(now.dist),
        ra=_out(now.ra), dec=_out(now.dec),
        lon_speed=_out(lon_s), lat_speed=_out(lat_s), dist_speed=_out(dist_s))
