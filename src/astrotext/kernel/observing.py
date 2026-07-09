"""Fixed stars and sun rise/set for kernel v2 (KERNEL.md §8).

Fixed stars
-----------
Catalog: data/kernel/hipparcos_22.json — van Leeuwen 2007 (VizieR
I/311/hip2), ICRS epoch J1991.25, fetched by tools/fetch_hipparcos.py
(public ESA data; replaces sefstars.txt as the shipped source at K8).
Reduction per §4: `erfa.pmpx` (proper motion + parallax against the
observer's barycentric position), `erfa.ldsun` (solar deflection,
infinite-distance source), `erfa.ab` (aberration), shared BPN →
ecliptic of date.  Radial velocities are 0 (not in hip2; sub-0.01″/cy
for these 22 bright stars).  Parity vs swe_fixstar ≤ 0.5″ (both sides
are Hipparcos-derived; conjunction orb is 1°, display 1″).

Sun rise/set (planetary hours)
------------------------------
Root of the topocentric solar altitude against the SE-parity horizon:

    alt_target = H0_EFFECTIVE − SD(t),   SD = 959.63″ / dist_au

H0_EFFECTIVE = −0.61233° is calibrated black-box (§11): the altitude
our own pipeline computes for the sun's center at SE 2.10.03's
reported rise/set instants, stable to ±0.7″ over latitudes ±60°,
seasons and centuries (= ±0.05 s of time).  It absorbs SE's refraction
model and limb convention as a single constant; the textbook
−34′ − SD would miss SE by ~2.2′ ≈ 9 s.  The altitude function applies
the geocentric→topocentric parallax term (8.794″/dist · cos alt).

Search: 15-min bracketing scan from the start instant, bisection to
1e-8 day (≈ 1 ms).  Circumpolar days return None (no crossing within
the scan window) — the engine's polar flags stay unchanged (§7 spirit).
Acceptance: fixture rise/set within ±1 s of swe_rise_trans.
"""
from __future__ import annotations

import functools
import json

import erfa
import numpy as np

from ..config import kernel_data_path
from . import bodies as kb
from .frames import Frames, gst06a, vec_to_sph
from . import timescales as kts

__all__ = ["STAR_NAMES", "star_apparent", "next_sun_event"]

H0_EFFECTIVE_DEG = -0.61233           # calibrated vs SE (see module doc)
_SD_CONST = 959.63 / 3600.0           # solar semi-diameter at 1 au, deg
_PARALLAX_CONST = 8.794 / 3600.0      # solar parallax at 1 au, deg


@functools.lru_cache(maxsize=1)
def _catalog() -> dict:
    path = kernel_data_path() / "hipparcos_22.json"
    return json.loads(path.read_text())


def _catalog_epoch_jd() -> float:
    return float(_catalog()["epoch_jd_tt"])


STAR_NAMES: tuple[str, ...] = tuple(
    json.loads((kernel_data_path() / "hipparcos_22.json").read_text())
    ["stars"].keys()) if (kernel_data_path() / "hipparcos_22.json").exists() \
    else ()


def star_apparent(name: str, jd_tt) -> kb.Apparent:
    """Apparent ecliptic-of-date lon/lat (+RA/dec) of a catalog star."""
    cat = _catalog()["stars"]
    try:
        s = cat[name]
    except KeyError:
        raise KeyError(f"unknown star {name!r}; have {sorted(cat)}") from None
    jd = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    frames = Frames.at(jd)
    pe, ve = kb.state_ssb("earth", jd)                  # au, au/day
    ps, _ = kb.state_ssb("sun", jd)
    pmt = (jd - _catalog_epoch_jd()) / 365.25           # years since epoch
    ra_r, dec_r = np.radians(s["ra_deg"]), np.radians(s["dec_deg"])
    pr = np.radians(s["pmra_masyr"] / 3.6e6) / np.cos(dec_r)
    pd = np.radians(s["pmde_masyr"] / 3.6e6)
    px = s["plx_mas"] / 1000.0                          # arcsec
    u = erfa.pmpx(ra_r, dec_r, pr, pd, px, 0.0, pmt, pe.T)
    eh = (pe - ps).T
    em = np.linalg.norm(eh, axis=1)
    u = erfa.ldsun(u, eh / em[:, None], em)
    v = (ve / kb.C_AUD).T
    bm1 = np.sqrt(1.0 - np.sum(v * v, axis=1))
    u = erfa.ab(u, v, em, bm1)
    u_equ = np.einsum("...ij,...j->...i", frames.rbpn, u)
    ra, dec, _ = vec_to_sph(u_equ)
    u_ecl = np.einsum("...ij,...j->...i", frames.recl, u)
    lon, lat, _ = vec_to_sph(u_ecl)

    def _o(x):
        return float(x[0]) if np.ndim(jd_tt) == 0 else x

    return kb.Apparent(lon=_o(lon), lat=_o(lat), dist=_o(np.full(len(jd),
                       np.inf)), ra=_o(ra), dec=_o(dec))


def true_altitude(jd_ut: float, ecl_lon: float, ecl_lat: float,
                  geolat: float, geolon: float) -> float:
    """Geocentric true altitude (deg) of an ecliptic-of-date position —
    swe_azalt(ECL2HOR)[1] parity (measured exact: SE applies no diurnal
    parallax to the supplied geocentric coordinates)."""
    jd_tt = kts.ut1_to_tt(jd_ut, "swieph")
    from .frames import true_obliquity
    eps = true_obliquity(jd_tt)
    lam, bet = np.radians(ecl_lon), np.radians(ecl_lat)
    x = np.cos(bet) * np.cos(lam)
    y = np.cos(eps) * np.cos(bet) * np.sin(lam) - np.sin(eps) * np.sin(bet)
    z = np.sin(eps) * np.cos(bet) * np.sin(lam) + np.cos(eps) * np.sin(bet)
    ra = np.arctan2(y, x)
    dec = np.arcsin(np.clip(z, -1.0, 1.0))
    gast = gst06a(jd_ut, jd_tt)
    h = gast + np.radians(geolon) - ra
    phi = np.radians(geolat)
    return float(np.degrees(np.arcsin(np.clip(
        np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(h),
        -1.0, 1.0))))


# ------------------------------------------------------------- rise/set

def _sun_alt_minus_target(jd_ut, lat, lon):
    """Topocentric solar altitude minus the rise/set target altitude."""
    jd_tt = kts.ut1_to_tt(jd_ut, "swieph")
    a = kb.apparent("sun", jd_tt)
    gast = np.degrees(gst06a(jd_ut, jd_tt))
    h = np.radians((np.asarray(gast) + lon - a.ra) % 360.0)
    phi = np.radians(lat)
    dec = np.radians(a.dec)
    alt = np.degrees(np.arcsin(np.clip(
        np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(h),
        -1.0, 1.0)))
    alt = alt - _PARALLAX_CONST / a.dist * np.cos(np.radians(alt))
    target = H0_EFFECTIVE_DEG - _SD_CONST / a.dist
    return alt - target


def next_sun_event(jd_ut_start: float, lat: float, lon: float,
                   kind: str = "rise", scan_days: float = 1.5
                   ) -> float | None:
    """First sun rise/set strictly after jd_ut_start; None if none is
    found within ``scan_days`` (circumpolar regime — caller flags)."""
    if kind not in ("rise", "set"):
        raise ValueError("kind must be 'rise' or 'set'")
    step = 1.0 / 96.0                                   # 15 minutes
    ts = np.arange(jd_ut_start, jd_ut_start + scan_days + step, step)
    f = np.asarray(_sun_alt_minus_target(ts, lat, lon))  # vectorized scan
    for i in range(len(ts) - 1):
        a, b = f[i], f[i + 1]
        want = (a < 0.0 <= b) if kind == "rise" else (a >= 0.0 > b)
        if not want:
            continue
        lo, hi = float(ts[i]), float(ts[i + 1])
        flo = float(a)
        for _ in range(45):                             # → ~1e-8 day
            mid = 0.5 * (lo + hi)
            fm = float(_sun_alt_minus_target(mid, lat, lon))
            if (fm < 0.0) == (flo < 0.0):
                lo, flo = mid, fm
            else:
                hi = mid
        return 0.5 * (lo + hi)
    return None
