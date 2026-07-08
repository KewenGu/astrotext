#!/usr/bin/env python3
"""K0 probe — de440 + pyerfa reduction pipeline vs swetest.

Throwaway per KERNEL.md §12: Sun/Moon/Mars apparent ecliptic longitude
over ~20 instants spanning 1800-2399, TT time scale fed to both sides
(isolates the planetary pipeline from the ΔT model, which is K1).

Pipeline (KERNEL.md §4): SPK barycentric states -> light-time x2 ->
solar deflection (erfa.ld, finite-distance q; skipped for Sun) ->
annual aberration (erfa.ab) -> bias-precession-nutation (erfa.pnm06a)
-> ecliptic-of-date via true obliquity (erfa.obl06 + nut06a de).

Usage: k0_probe.py <de440.bsp> <swetest-bin> <ephe-dir>
"""
import subprocess
import sys
import time

import erfa
import numpy as np
from jplephem.spk import SPK

AU_KM = 149597870.7            # IAU 2012 resolution B2
C_KM_S = 299792.458
C_AUD = C_KM_S * 86400.0 / AU_KM   # speed of light in au/day

BSP, SWETEST, EPHE = sys.argv[1], sys.argv[2], sys.argv[3]

kernel = SPK.open(BSP)
SEG_SSB = {n: kernel[0, n] for n in range(1, 11)}   # barycenters + Sun(10)
SEG_EMB_EARTH = kernel[3, 399]
SEG_EMB_MOON = kernel[3, 301]
SEG_MER = kernel[1, 199]
SEG_VEN = kernel[2, 299]


def _state(seg, jd):
    p, v = seg.compute_and_differentiate(jd)
    return p / AU_KM, v / AU_KM          # au, au/day


def ssb_state(body, jd):
    """Barycentric ICRF state. body: 'sun','moon','earth', or planet index."""
    if body == "earth":
        p1, v1 = _state(SEG_SSB[3], jd)
        p2, v2 = _state(SEG_EMB_EARTH, jd)
        return p1 + p2, v1 + v2
    if body == "moon":
        p1, v1 = _state(SEG_SSB[3], jd)
        p2, v2 = _state(SEG_EMB_MOON, jd)
        return p1 + p2, v1 + v2
    if body == "sun":
        return _state(SEG_SSB[10], jd)
    if body == 1:
        p1, v1 = _state(SEG_SSB[1], jd)
        p2, v2 = _state(SEG_MER, jd)
        return p1 + p2, v1 + v2
    if body == 2:
        p1, v1 = _state(SEG_SSB[2], jd)
        p2, v2 = _state(SEG_VEN, jd)
        return p1 + p2, v1 + v2
    return _state(SEG_SSB[body], jd)     # Mars..Pluto barycenters (SE does same)


def apparent(body, jd_tt):
    """Geocentric apparent ecliptic-of-date lon/lat (deg), distance (au)."""
    pe, ve = ssb_state("earth", jd_tt)
    pb, _ = ssb_state(body, jd_tt)
    # light-time: 2 iterations on the antedated body position
    tau = np.linalg.norm(pb - pe) / C_AUD
    for _ in range(2):
        pb, _ = ssb_state(body, jd_tt - tau)
        tau = np.linalg.norm(pb - pe) / C_AUD
    p = pb - pe
    dist = np.linalg.norm(p)
    u = p / dist
    # solar gravitational deflection (not for the Sun itself)
    if body != "sun":
        ps, _ = ssb_state("sun", jd_tt)
        eh = pe - ps
        em = np.linalg.norm(eh)
        q = pb - ps
        q = q / np.linalg.norm(q)
        u = erfa.ld(1.0, u, q, eh / em, em, 1e-9)
    else:
        em = dist
    # annual aberration (relativistic; observer = geocenter)
    v = ve / C_AUD                       # velocity in units of c
    bm1 = np.sqrt(1.0 - np.dot(v, v))
    u = erfa.ab(u, v, em, bm1)
    # frame bias + precession + nutation (IAU 2006/2000A)
    rbpn = erfa.pnm06a(jd_tt, 0.0)
    u = rbpn @ u
    # equatorial -> ecliptic of date (true obliquity)
    eps = erfa.obl06(jd_tt, 0.0) + erfa.nut06a(jd_tt, 0.0)[1]
    ce, se = np.cos(eps), np.sin(eps)
    x, y, z = u
    xe, ye, ze = x, ce * y + se * z, -se * y + ce * z
    lon = np.degrees(np.arctan2(ye, xe)) % 360.0
    lat = np.degrees(np.arcsin(np.clip(ze, -1, 1)))
    return lon, lat, dist


def swetest_ref(ipl, jd_tt):
    """swetest reference: -bj treats input as TT(ET). Returns lon,lat,dist."""
    out = subprocess.run(
        [SWETEST, "-bj%.9f" % float(jd_tt), f"-p{ipl}", "-fPlbR", "-g,", "-head",
         f"-edir{EPHE}"],
        capture_output=True, text=True, check=True).stdout.strip()
    parts = out.split(",")
    return float(parts[1]), float(parts[2]), float(parts[3])


def wrap_asec(d):
    return ((d + 180.0) % 360.0 - 180.0) * 3600.0


BODIES = [("Sun", "sun", 0), ("Moon", "moon", 1), ("Mars", 4, 4)]

rng = np.random.default_rng(42)
JD0, JD1 = 2378497.0, 2597641.0          # 1800-01-01 .. 2399-12-31
instants = np.sort(rng.uniform(JD0, JD1, 20))

hdr_lon, hdr_lat = 'max|dlon|"', 'max|dlat|"'
print(f"{'body':6} {hdr_lon:>12} {hdr_lat:>12} {'max|ddist| au':>14}")
worst = 0.0
for name, key, ipl in BODIES:
    dl = db = dr = 0.0
    for jd in instants:
        lon, lat, dist = apparent(key, jd)
        slon, slat, sdist = swetest_ref(ipl, jd)
        dl = max(dl, abs(wrap_asec(lon - slon)))
        db = max(db, abs(wrap_asec(lat - slat)))
        dr = max(dr, abs(dist - sdist))
    worst = max(worst, dl, db)
    print(f"{name:6} {dl:12.5f} {db:12.5f} {dr:14.3e}")

# ---- performance: per body-instant cost of the full pipeline ----
t0 = time.perf_counter()
N = 0
for jd in instants:
    for _, key, _ in BODIES:
        apparent(key, jd)
        N += 1
dt = (time.perf_counter() - t0) / N * 1e6
print(f"\nperf: {dt:.0f} us per body-instant (scalar, unvectorized)")
print(f"gate: worst angular error {worst:.5f}\" vs 0.01\" target")
