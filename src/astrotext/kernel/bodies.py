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


_SEG_TABLES: dict[int, tuple[float, float, np.ndarray]] = {}


def _seg_table(seg):
    """Extract a Type-2 segment's Chebyshev table once (numpy arrays).

    jplephem's per-call ``generate`` costs ~30-90 µs of Python/DAF
    bookkeeping; root-finding makes 10⁵ scalar segment evaluations per
    dossier, so we evaluate the same coefficients ourselves (identical
    math — differences at the 1e-15 au float floor; the kernel fixture
    suite guards this).  SPK Type 2 record layout: [MID, RADIUS,
    x-coeffs…, y…, z…]; segment footer [INIT, INTLEN, RSIZE, N].
    """
    tbl = _SEG_TABLES.get(id(seg))
    if tbl is None:
        arr = np.array(seg.daf.map_array(seg.start_i, seg.end_i))
        init, intlen, rsize, n = arr[-4:]
        n, rsize = int(n), int(rsize)
        ncoef = (rsize - 2) // 3
        coef = np.ascontiguousarray(
            arr[: n * rsize].reshape(n, rsize)[:, 2:].reshape(n, 3, ncoef))
        # derivative coefficients precomputed once (chebder equivalent)
        der = np.zeros((n, 3, ncoef))
        if ncoef >= 2:
            der[..., ncoef - 2] = 2.0 * (ncoef - 1) * coef[..., ncoef - 1]
            for j in range(ncoef - 3, -1, -1):
                der[..., j] = der[..., j + 2] + 2.0 * (j + 1) * coef[..., j + 1]
            der[..., 0] *= 0.5
        tbl = (float(init), float(intlen), coef, der)
        _SEG_TABLES[id(seg)] = tbl
    return tbl


def _clenshaw(c, x):
    """Chebyshev series at x; c shape (..., ncoef), x broadcastable."""
    b1 = np.zeros_like(c[..., 0])
    b2 = np.zeros_like(b1)
    x2 = 2.0 * x
    for j in range(c.shape[-1] - 1, 0, -1):
        b1, b2 = x2 * b1 - b2 + c[..., j], b1
    return x * b1 - b2 + c[..., 0]


_REC_CACHE: dict[tuple[int, int], tuple] = {}


def _clenshaw_py(c, x):
    b1 = 0.0
    b2 = 0.0
    x2 = 2.0 * x
    for j in range(len(c) - 1, 0, -1):
        b1, b2 = x2 * b1 - b2 + c[j], b1
    return x * b1 - b2 + c[0]


def _seg_state(seg, jd):
    """Type-2 Chebyshev state (au, au/day) via the cached tables.

    Scalars run a pure-float Clenshaw over per-record coefficient lists
    (numpy's small-array op overhead is ~20× the arithmetic here;
    root-finding revisits the same records constantly, so the lists are
    memoized).  Arrays use the vectorized Clenshaw."""
    init, intlen, coef, der = _seg_table(seg)
    dscale = (2.0 / intlen) * 86400.0          # d/dx -> per day
    if np.ndim(jd) == 0 or (hasattr(jd, "size") and jd.size == 1):
        jd_s = float(jd if np.ndim(jd) == 0 else np.asarray(jd).ravel()[0])
        t = (jd_s - 2451545.0) * 86400.0
        k = int((t - init) // intlen)
        k = 0 if k < 0 else (len(coef) - 1 if k >= len(coef) else k)
        key = (id(seg), k)
        rec = _REC_CACHE.get(key)
        if rec is None:
            rec = (coef[k].tolist(), der[k].tolist())
            _REC_CACHE[key] = rec
        x = 2.0 * (t - init - k * intlen) / intlen - 1.0
        cl, dl = rec
        pos = np.array([_clenshaw_py(cl[0], x), _clenshaw_py(cl[1], x),
                        _clenshaw_py(cl[2], x)]) / AU_KM
        vel = np.array([_clenshaw_py(dl[0], x) * dscale,
                        _clenshaw_py(dl[1], x) * dscale,
                        _clenshaw_py(dl[2], x) * dscale]) / AU_KM
        if np.ndim(jd) == 0:
            return pos, vel
        return pos[:, None], vel[:, None]
    t = (np.asarray(jd, dtype=float) - 2451545.0) * 86400.0
    k = np.clip(((t - init) // intlen).astype(int), 0, len(coef) - 1)
    x = 2.0 * (t - init - k * intlen) / intlen - 1.0
    c = coef[k]                                # (n, 3, ncoef)
    d = der[k]
    xx = x[:, None]                            # broadcast over axes
    pos = _clenshaw(c, xx).T                   # (3, n)
    vel = (_clenshaw(d, xx) * dscale).T
    return pos / AU_KM, vel / AU_KM


@functools.lru_cache(maxsize=16384)
def _earth_sun_scalar(body: str, jd: float):
    return _state_ssb_raw(body, np.array([jd]))


def state_ssb(body: str, jd):
    """Barycentric ICRF (position, velocity) in au, au/day. Vectorized:
    jd may be scalar or (n,); arrays come back as (3,) / (3, n).
    Scalar earth/sun states are memoized: every body at the same instant
    reuses them (14x fan-out in states()/root-finding)."""
    if body in ("earth", "sun"):
        j = np.atleast_1d(np.asarray(jd, dtype=float))
        if j.size == 1:
            return _earth_sun_scalar(body, float(j[0]))
    return _state_ssb_raw(body, jd)


def _state_ssb_raw(body: str, jd):
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


@functools.lru_cache(maxsize=1)
def _j2000_matrices():
    """Fixed rotations for the frame='j2000' mode (SE FLG_J2000|FLG_NONUT
    semantics, pinned black-box: frame bias IS applied — without it SE
    differs by ~6.5 mas).  Returns (rb, recl_j2000)."""
    rb, _, _ = erfa.bp06(2451545.0, 0.0)
    eps0 = erfa.obl06(2451545.0, 0.0)
    ce, se = np.cos(eps0), np.sin(eps0)
    r1 = np.array([[1.0, 0.0, 0.0], [0.0, ce, se], [0.0, -se, ce]])
    return rb, r1 @ rb


def apparent(body: str, jd_tt, frames: Frames | None = None,
             frame: str = "of-date") -> Apparent:
    """Full §4 reduction at jd_tt (scalar or (n,) array).

    frame="of-date" (default): true equator/equinox + ecliptic of date.
    frame="j2000": mean ecliptic & equinox of J2000, no nutation — the
    fixed frame used by precession-corrected returns (SE
    FLG_J2000|FLG_NONUT parity ≤0.0002″, measured).
    """
    jd = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    if frames is None and frame == "of-date":
        from .frames import bundle
        frames = bundle(jd)
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
    if frame == "j2000":
        rb, recl0 = _j2000_matrices()
        u_equ = np.einsum("ij,...j->...i", rb, u)
        u_ecl = np.einsum("ij,...j->...i", recl0, u)
    else:
        u_equ = np.einsum("...ij,...j->...i", frames.rbpn, u)
        u_ecl = np.einsum("...ij,...j->...i", frames.recl, u)
    ra, dec, _ = vec_to_sph(u_equ)
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
    ra_speed: object = 0.0     # °/day (internal consumers only)
    dec_speed: object = 0.0    # °/day


def _wrap_diff(a, b):
    """(a − b) with longitude wrap, in degrees."""
    return (np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0


def stencil_speeds(f, jd_tt, **kw) -> ApparentSpeed:
    """Five-point-stencil speeds of any Apparent-producing function.

    f'(t) = [8(f(t+h) − f(t−h)) − (f(t+2h) − f(t−2h))] / 12h, with
    lon/RA differences taken wrap-safe.  Shared by bodies, derived
    points and sidereal speeds.
    """
    jd = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    now = f(jd, **kw)
    m1, p1 = f(jd - _SPEED_H, **kw), f(jd + _SPEED_H, **kw)
    m2, p2 = f(jd - 2.0 * _SPEED_H, **kw), f(jd + 2.0 * _SPEED_H, **kw)
    den = 12.0 * _SPEED_H

    def _five(f_p1, f_m1, f_p2, f_m2, wrap):
        d1 = _wrap_diff(f_p1, f_m1) if wrap else np.asarray(f_p1) - f_m1
        d2 = _wrap_diff(f_p2, f_m2) if wrap else np.asarray(f_p2) - f_m2
        return (8.0 * d1 - d2) / den

    def _out(x):
        x = np.atleast_1d(x)
        return float(x[0]) if np.isscalar(jd_tt) or np.ndim(jd_tt) == 0 else x

    return ApparentSpeed(
        lon=_out(now.lon), lat=_out(now.lat), dist=_out(now.dist),
        ra=_out(now.ra), dec=_out(now.dec),
        lon_speed=_out(_five(p1.lon, m1.lon, p2.lon, m2.lon, True)),
        lat_speed=_out(_five(p1.lat, m1.lat, p2.lat, m2.lat, False)),
        dist_speed=_out(_five(p1.dist, m1.dist, p2.dist, m2.dist, False)),
        ra_speed=_out(_five(p1.ra, m1.ra, p2.ra, m2.ra, True)),
        dec_speed=_out(_five(p1.dec, m1.dec, p2.dec, m2.dec, False)))


def apparent_with_speed(body: str, jd_tt, frame: str = "of-date"
                        ) -> ApparentSpeed:
    """§4 step 7: light-time-consistent speeds (see stencil_speeds).
    One Frames per sample instant (shared across bodies only when the
    caller batches instants — the dossier path batches, root-finding
    refines)."""
    return stencil_speeds(
        lambda j, **kw: apparent(body, j, **kw), jd_tt, frame=frame)
