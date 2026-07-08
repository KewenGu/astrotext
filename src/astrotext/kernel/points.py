"""Derived lunar points for kernel v2 — nodes and mean apogee (§6).

TRUE_NODE — osculating ascending node of the momentary geocentric lunar
orbit (SE manual §2.2.2: "intersection line of the momentary orbital
plane of the Moon and the plane of the ecliptic").  Computed from the
geometric (no light-time, no aberration) DE440 geocentric lunar state
rotated into the true-ecliptic-of-date frame: with h = r × v,
Ω = atan2(h_x, −h_y); latitude is 0 by construction.  Distance is the
osculating-ellipse radius at the node, r = p / (1 + e·cos ν_node) with
μ = GM(Earth) + GM(Moon) (DE440 header values).

MEAN_NODE / MEAN_APOGEE (Lilith) — mean lunar elements, Chapront
ELP-2000/82 as published in Meeus, *Astronomical Algorithms* 2nd ed.,
ch. 47 (referred to the mean equinox of date; T = Julian centuries TDB
from J2000):

  Ω  = 125.0445479 − 1934.1362891 T + 0.0020754 T² + T³/467441
       − T⁴/60616000
  ϖ  =  83.3532465 + 4069.0137287 T − 0.0103200 T² − T³/80053
       + T⁴/18999000          (mean longitude of perigee; apogee = ϖ+180°)

ϖ is the usual dog-leg angle (node along the ecliptic, then along the
orbit), so the apogee sits at argument u = ϖ + 180° − Ω *along the mean
orbit*, inclined i = 5.145396°.  Per the SE manual (§2.2.1) the point is
projected onto the ecliptic — that projection (≈ (i²/4)·sin 2u, up to
±7′) and the resulting latitude β = asin(sin i · sin u) are exactly
SE's convention.  Longitudes get nutation Δψ added to refer them to the
true equinox of date (as every longitude in the engine).

Parity vs SE (KERNEL.md §6): SE's mean points come from *Moshier's*
adjustment of ELP-2000-85 plus DE431-derived corrections (manual
§2.2.1, "estimated precision 1″"); the published-polynomial route is
kept deliberately (clean-room; do not fit SE's corrections) and the
measured gap — ≤0.6″ node, ≤2″ apogee across 1800–2399 — is documented
and gated in tools/verify_kernel.py.  Display precision is 1″.

Speeds: 5-point stencil, as in bodies.py.
"""
from __future__ import annotations

import numpy as np

from . import bodies as kb
from .bodies import Apparent, ApparentSpeed, _SPEED_H, _wrap_diff
from .frames import Frames, ecl_matrix, nutation

# GM values, DE440 header (km^3/s^2), converted to au^3/day^2
_GM_EARTH_KM = 398600.435507
_GM_MOON_KM = 4902.800118
_KM3S2_TO_AU3D2 = (86400.0 ** 2) / (kb.AU_KM ** 3)
MU_GEO = (_GM_EARTH_KM + _GM_MOON_KM) * _KM3S2_TO_AU3D2

MEAN_INCLINATION_DEG = 5.145396          # ELP-2000 mean orbit (Meeus ch. 47)

# SE returns constant mean-orbit radii for the mean points (measured;
# matched to <3e-10 au): node at a(1−e²) shape, apogee at a(1+e).
MEAN_NODE_DIST_AU = 0.0025695552898
MEAN_APOGEE_DIST_AU = 0.0027106251317

POINTS = ("true_node", "mean_node", "mean_apogee")


def _moon_geo_state(jd):
    """Geometric geocentric lunar state, ICRS, au / au/day; jd (n,)."""
    pm, vm = kb.state_ssb("moon", jd)
    pe, ve = kb.state_ssb("earth", jd)
    return pm - pe, vm - ve


def true_node(jd_tt) -> Apparent:
    """Osculating ascending node; vectorized like bodies.apparent."""
    jd = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    r_icrs, v_icrs = _moon_geo_state(jd)             # (3, n)
    recl = ecl_matrix(jd)                            # (n, 3, 3)
    r = np.einsum("nij,jn->ni", recl, r_icrs)        # (n, 3) ecliptic frame
    v = np.einsum("nij,jn->ni", recl, v_icrs)
    h = np.cross(r, v)                               # (n, 3)
    lon = np.degrees(np.arctan2(h[:, 0], -h[:, 1])) % 360.0
    # osculating ellipse radius at the node
    hh = np.einsum("ni,ni->n", h, h)
    p = hh / MU_GEO
    rn = np.linalg.norm(r, axis=1)
    evec = np.cross(v, h) / MU_GEO - r / rn[:, None]
    e = np.linalg.norm(evec, axis=1)
    nvec = np.stack([-h[:, 1], h[:, 0], np.zeros(len(jd))], axis=1)
    nn = np.linalg.norm(nvec, axis=1)
    cosnu = np.einsum("ni,ni->n", evec, nvec) / np.where(
        e * nn == 0.0, 1.0, e * nn)
    dist = p / (1.0 + e * np.clip(cosnu, -1.0, 1.0))
    # RA/dec of the node direction (unit vector at lat 0 in ecliptic frame)
    lam = np.radians(lon)
    u_ecl = np.stack([np.cos(lam), np.sin(lam), np.zeros(len(jd))], axis=1)
    u_equ = np.einsum("nji,nj->ni", recl, u_ecl)     # transpose: ecl -> equ(ICRS)
    fr = Frames.at(jd)
    u_equ = np.einsum("nij,nj->ni", fr.rbpn, u_equ)
    from .frames import vec_to_sph
    ra, dec, _ = vec_to_sph(u_equ)

    def _o(x):
        return float(x[0]) if np.ndim(jd_tt) == 0 else x

    return Apparent(lon=_o(lon), lat=_o(np.zeros(len(jd))), dist=_o(dist),
                    ra=_o(ra), dec=_o(dec))


def _mean_elements(jd):
    t = (np.asarray(jd, dtype=float) - 2451545.0) / 36525.0
    node = (125.0445479 - 1934.1362891 * t + 0.0020754 * t * t
            + t ** 3 / 467441.0 - t ** 4 / 60616000.0)
    perigee = (83.3532465 + 4069.0137287 * t - 0.0103200 * t * t
               - t ** 3 / 80053.0 + t ** 4 / 18999000.0)
    return node % 360.0, perigee % 360.0


def _dpsi_deg(jd):
    return np.degrees(nutation(jd)[0])


def mean_node(jd_tt) -> Apparent:
    jd = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    node, _ = _mean_elements(jd)
    lon = (node + _dpsi_deg(jd)) % 360.0
    return _mean_point_output(jd_tt, jd, lon, np.zeros(len(jd)),
                              np.full(len(jd), MEAN_NODE_DIST_AU))


def mean_apogee(jd_tt) -> Apparent:
    jd = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    node, perigee = _mean_elements(jd)
    u = np.radians((perigee + 180.0) - node)         # along-orbit arg of apogee
    i = np.radians(MEAN_INCLINATION_DEG)
    lam = node + np.degrees(np.arctan2(np.sin(u) * np.cos(i), np.cos(u)))
    beta = np.degrees(np.arcsin(np.sin(u) * np.sin(i)))
    lon = (lam + _dpsi_deg(jd)) % 360.0
    return _mean_point_output(jd_tt, jd, lon, beta,
                              np.full(len(jd), MEAN_APOGEE_DIST_AU))


def _mean_point_output(jd_orig, jd, lon, lat, dist) -> Apparent:
    """RA/dec via SE's convention: the true-equinox (lon, lat) pair is
    treated as ecliptic-of-date coordinates and rotated by the true
    obliquity to the true equator (swe_cotrans semantics)."""
    from .frames import true_obliquity, vec_to_sph
    lam, bet = np.radians(lon), np.radians(lat)
    u_ecl = np.stack([np.cos(bet) * np.cos(lam), np.cos(bet) * np.sin(lam),
                      np.sin(bet)], axis=1)
    eps = true_obliquity(jd)
    ce, se = np.cos(eps), np.sin(eps)
    x, y, z = u_ecl[:, 0], u_ecl[:, 1], u_ecl[:, 2]
    u_equ = np.stack([x, ce * y - se * z, se * y + ce * z], axis=1)
    ra, dec, _ = vec_to_sph(u_equ)

    def _o(x_):
        return float(x_[0]) if np.ndim(jd_orig) == 0 else x_

    return Apparent(lon=_o(lon), lat=_o(np.asarray(lat, dtype=float)),
                    dist=_o(dist), ra=_o(ra), dec=_o(dec))


_FUNCS = {"true_node": true_node, "mean_node": mean_node,
          "mean_apogee": mean_apogee}


def apparent(point: str, jd_tt) -> Apparent:
    return _FUNCS[point](jd_tt)


def apparent_with_speed(point: str, jd_tt) -> ApparentSpeed:
    f = _FUNCS[point]
    jd = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    now = f(jd)
    m1, p1 = f(jd - _SPEED_H), f(jd + _SPEED_H)
    m2, p2 = f(jd - 2 * _SPEED_H), f(jd + 2 * _SPEED_H)
    den = 12.0 * _SPEED_H

    def _five(fp1, fm1, fp2, fm2, wrap):
        d1 = _wrap_diff(fp1, fm1) if wrap else np.asarray(fp1) - fm1
        d2 = _wrap_diff(fp2, fm2) if wrap else np.asarray(fp2) - fm2
        return (8.0 * d1 - d2) / den

    def _o(x):
        x = np.atleast_1d(x)
        return float(x[0]) if np.ndim(jd_tt) == 0 else x

    return ApparentSpeed(
        lon=_o(now.lon), lat=_o(now.lat), dist=_o(now.dist),
        ra=_o(now.ra), dec=_o(now.dec),
        lon_speed=_o(_five(p1.lon, m1.lon, p2.lon, m2.lon, True)),
        lat_speed=_o(_five(p1.lat, m1.lat, p2.lat, m2.lat, False)),
        dist_speed=_o(_five(p1.dist, m1.dist, p2.dist, m2.dist, False)))
