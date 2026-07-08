"""House systems for kernel v2 — clean-room (KERNEL.md §7).

Written from the constructive definitions in the published literature
(Holden, *House Division*; Munkasey's formulary; standard spherical
astronomy) and pinned black-box against ``swe_houses_armc`` — the SE
source tree stayed closed.

Inputs: ARMC θ (deg), true obliquity ε (deg), geographic latitude φ
(deg).  ``armc_deg`` builds θ from `erfa.gst06a` + east longitude; house
math itself never touches time.

Geometry (equatorial frame of date, x → equinox, z → north pole):

  zenith        Z = (cos φ cos θ, cos φ sin θ, sin φ)
  north point   N = (−sin φ cos θ, −sin φ sin θ, cos φ)
  east point    E = N × Z          (on horizon, RA θ+90 at the equator)
  ecliptic pole n = (0, −sin ε, cos ε)

  MC     : ecliptic point with RA = θ (λ = atan2(sin θ, cos θ cos ε))
  ASC    : eastern intersection of horizon and ecliptic: lon(n × Z)
  Vertex : western intersection of prime vertical and ecliptic; the
           prime vertical's plane normal is N, so lon(N × n)
  EqAsc  : ASC formula at φ = 0 (the "equatorial ascendant"/East point)

Systems:

  Equal (A)        cusp_i = ASC + 30(i−1)
  Whole sign (W)   cusp_1 = 30·⌊ASC/30⌋, then 30° steps
  Porphyry (O)     ecliptic arcs MC→ASC and ASC→IC trisected
  Regiomontanus (R) house circles through N,S and the equator point at
                   RA θ+D (D = 30,60,120,150 for cusps 11,12,2,3):
                   cusp = lon(±(N × e_D) × n), sign chosen so the cusp
                   lies in the eastern half (RA−θ ∈ (0,180) with D)
  Campanus (C)     same house circles but through the prime-vertical
                   point v_D = E cos D + Z sin D
  Alcabitius (B)   the ASC's diurnal semi-arc SA_d = 90 + AD(ASC),
                   AD = asin(tan φ tan δ); cusps 11,12 at
                   RA = θ + k/3·SA_d, cusps 2,3 mirrored on the
                   nocturnal side (hour-circle projection to the
                   ecliptic, i.e. the MC formula at that RA)
  Koch (K)         ascendants taken at shifted sidereal times built
                   from the MC degree's semi-arc (pinned black-box:
                   cusp 11 at θ' = θ + SA_d(δ_MC)/3·…, see code)
  Placidus (P)     cusp λ solves  RA(λ) − θ = k/3 · SA(δ(λ));
                   fixed-point iteration seeded with Porphyry
                   (≈6-8 iterations, we run 25; converges everywhere
                   the system is defined)

Polar: AD = asin(tan φ tan δ) has no solution beyond the polar circles
for Placidus/Koch (and Alcabitius when the ASC degree is circumpolar):
:class:`PolarHousesError` is raised; the engine's existing
``polar_fallback`` semantics stay outside the kernel (§7).

Acceptance (tools/verify_kernel.py): every system ≤ 0.001″ vs
``swe_houses_armc`` at identical (θ, ε, φ) over the seeded grid ×
latitudes {0, ±31.911, ±48.4, ±59.93, ±66.99}; the θ time-chain itself
is gated separately (ARMC vs SE ≤ 0.01″, the K1 frame gap).
"""
from __future__ import annotations

import numpy as np

from .frames import gst06a

__all__ = ["PolarHousesError", "armc_deg", "angles", "cusps", "SYSTEMS"]

SYSTEMS = ("P", "K", "O", "R", "C", "A", "W", "B")


class PolarHousesError(ValueError):
    """House system undefined at this latitude/obliquity configuration."""


def armc_deg(jd_ut1, jd_tt, geolon_east: float) -> float:
    """ARMC = Greenwich apparent sidereal time + east longitude, degrees."""
    return (np.degrees(gst06a(jd_ut1, jd_tt)) + geolon_east) % 360.0


# ---------------------------------------------------------------- geometry

def _lon_of(vec, eps_r):
    """Ecliptic longitude (deg) of an equatorial-frame vector."""
    x, y, z = vec
    ce, se = np.cos(eps_r), np.sin(eps_r)
    ye = ce * y + se * z
    return float(np.degrees(np.arctan2(ye, x))) % 360.0


def _ecl_point_at_ra(ra_deg, eps_r):
    """Longitude of the ecliptic point with the given right ascension."""
    ra = np.radians(ra_deg)
    return float(np.degrees(
        np.arctan2(np.sin(ra), np.cos(ra) * np.cos(eps_r)))) % 360.0


def _dec_of_lon(lon_deg, eps_r):
    """Declination (rad) of the ecliptic point at longitude lon."""
    lam = np.radians(lon_deg)
    return np.arcsin(np.clip(np.sin(eps_r) * np.sin(lam), -1.0, 1.0))


def _frame_vectors(armc, geolat):
    th, ph = np.radians(armc), np.radians(geolat)
    zen = np.array([np.cos(ph) * np.cos(th), np.cos(ph) * np.sin(th),
                    np.sin(ph)])
    north = np.array([-np.sin(ph) * np.cos(th), -np.sin(ph) * np.sin(th),
                      np.cos(ph)])
    east = np.cross(north, zen)
    return zen, north, east


def _ecl_pole(eps_r):
    return np.array([0.0, -np.sin(eps_r), np.cos(eps_r)])


def _asc_from_zenith(zen, east, eps_r):
    """Horizon ∩ ecliptic, taken in the EASTERN hemisphere (v·E > 0) —
    SE's convention; inside the polar circles the ecliptic's ascending
    node on the horizon can lie west, so a fixed cross-product
    orientation is not enough (measured: 180° flips at |lat| = 66.99)."""
    v = np.cross(_ecl_pole(eps_r), zen)
    if np.dot(v, east) < 0.0:
        v = -v
    return _lon_of(v, eps_r)


def angles(armc: float, eps_deg: float, geolat: float) -> dict[str, float]:
    """ASC, MC, ARMC, VERTEX, EQUATORIAL_ASC (degrees)."""
    eps_r = np.radians(eps_deg)
    zen, north, east = _frame_vectors(armc, geolat)
    mc = _ecl_point_at_ra(armc, eps_r)
    asc = _asc_from_zenith(zen, east, eps_r)
    # vertex: prime vertical (normal = N) ∩ ecliptic, WESTERN hemisphere
    v = np.cross(north, _ecl_pole(eps_r))
    if np.dot(v, east) > 0.0:
        v = -v
    vertex = _lon_of(v, eps_r)
    zen0, north0, east0 = _frame_vectors(armc, 0.0)
    eq_asc = _asc_from_zenith(zen0, east0, eps_r)
    return {"ASC": asc, "MC": mc, "ARMC": armc % 360.0,
            "VERTEX": vertex, "EQUATORIAL_ASC": eq_asc}


# ------------------------------------------------------------- semi-arcs

def _ascensional_difference(geolat, dec_r):
    """AD = asin(tan φ tan δ); PolarHousesError when |·| > 1."""
    x = np.tan(np.radians(geolat)) * np.tan(dec_r)
    if np.any(np.abs(x) > 1.0):
        raise PolarHousesError(
            "circumpolar configuration: ascensional difference undefined "
            f"(lat {geolat:.4f})")
    return np.degrees(np.arcsin(x))


def _circle_ecl_intersection(plane_normal, eps_r, armc, want_east):
    line = np.cross(plane_normal, _ecl_pole(eps_r))
    lon = _lon_of(line, eps_r)
    # eastern-half selection: hour angle of the cusp in (0, 180)
    ra = float(np.degrees(np.arctan2(line[1], line[0]))) % 360.0
    ha = (ra - armc) % 360.0
    if (0.0 < ha <= 180.0) != want_east:
        lon = (lon + 180.0) % 360.0
    return lon


# ------------------------------------------------------------- systems

def _cusps_equal(asc):
    return [(asc + 30.0 * i) % 360.0 for i in range(12)]


def _cusps_whole(asc):
    base = 30.0 * np.floor(asc / 30.0)
    return [(base + 30.0 * i) % 360.0 for i in range(12)]


def _cusps_porphyry(asc, mc):
    d = (asc - mc) % 360.0
    c = [0.0] * 12
    c[0] = asc
    c[9] = mc
    c[10] = (mc + d / 3.0) % 360.0
    c[11] = (mc + 2.0 * d / 3.0) % 360.0
    e = (mc + 180.0 - asc) % 360.0          # ASC -> IC arc
    c[1] = (asc + e / 3.0) % 360.0
    c[2] = (asc + 2.0 * e / 3.0) % 360.0
    for i in (3, 4, 5, 6, 7, 8):
        c[i] = (c[(i + 6) % 12] + 180.0) % 360.0
    return c


def _cusps_regiomontanus(armc, eps_r, geolat, asc, mc):
    _, north, _ = _frame_vectors(armc, geolat)
    c = [0.0] * 12
    c[0], c[9] = asc, mc
    for house, dd in ((10, 30.0), (11, 60.0), (1, 120.0), (2, 150.0)):
        ra = np.radians(armc + dd)
        e_d = np.array([np.cos(ra), np.sin(ra), 0.0])
        lon = _circle_ecl_intersection(np.cross(north, e_d), eps_r, armc,
                                       want_east=True)
        c[house] = lon
    for i in (3, 4, 5, 6, 7, 8):
        c[i] = (c[(i + 6) % 12] + 180.0) % 360.0
    return c


def _cusps_campanus(armc, eps_r, geolat, asc, mc):
    """Prime-vertical divisions D measured from the east point upward:
    ASC ↔ D=0, cusp 12 ↔ 30°, cusp 11 ↔ 60°, MC ↔ 90° (zenith); cusps
    2, 3 dip below the horizon on the eastern side (D = −30°, −60°)."""
    zen, north, east = _frame_vectors(armc, geolat)
    c = [0.0] * 12
    c[0], c[9] = asc, mc
    for house, dd in ((10, 60.0), (11, 30.0), (1, -30.0), (2, -60.0)):
        d = np.radians(dd)
        v = east * np.cos(d) + zen * np.sin(d)
        lon = _circle_ecl_intersection(np.cross(north, v), eps_r, armc,
                                       want_east=True)
        c[house] = lon
    for i in (3, 4, 5, 6, 7, 8):
        c[i] = (c[(i + 6) % 12] + 180.0) % 360.0
    return c


def _cusps_alcabitius(armc, eps_r, geolat, asc, mc):
    dec_asc = _dec_of_lon(asc, eps_r)
    ad = float(_ascensional_difference(geolat, dec_asc))
    sa_d = 90.0 + ad                          # diurnal semi-arc of the ASC
    sa_n = 90.0 - ad
    c = [0.0] * 12
    c[0], c[9] = asc, mc
    c[10] = _ecl_point_at_ra(armc + sa_d / 3.0, eps_r)
    c[11] = _ecl_point_at_ra(armc + 2.0 * sa_d / 3.0, eps_r)
    c[1] = _ecl_point_at_ra(armc + sa_d + sa_n / 3.0, eps_r)
    c[2] = _ecl_point_at_ra(armc + sa_d + 2.0 * sa_n / 3.0, eps_r)
    for i in (3, 4, 5, 6, 7, 8):
        c[i] = (c[(i + 6) % 12] + 180.0) % 360.0
    return c


def _asc_at(armc, eps_r, geolat):
    zen, _, east = _frame_vectors(armc, geolat)
    return _asc_from_zenith(zen, east, eps_r)


def _cusps_koch(armc, eps_r, geolat, asc, mc):
    """Ascendants at sidereal times θ ± k·SA_d/3, k = 1, 2, where SA_d
    is the diurnal semi-arc of the MC degree (pinned black-box: the
    shifts are symmetric about θ — cusp 11 at −2SA_d/3 … cusp 3 at
    +2SA_d/3 — exact to the solver's precision at three latitudes)."""
    dec_mc = _dec_of_lon(mc, eps_r)
    ad = float(_ascensional_difference(geolat, dec_mc))
    sa_d = 90.0 + ad
    c = [0.0] * 12
    c[0], c[9] = asc, mc
    c[10] = _asc_at(armc - 2.0 * sa_d / 3.0, eps_r, geolat)
    c[11] = _asc_at(armc - sa_d / 3.0, eps_r, geolat)
    c[1] = _asc_at(armc + sa_d / 3.0, eps_r, geolat)
    c[2] = _asc_at(armc + 2.0 * sa_d / 3.0, eps_r, geolat)
    for i in (3, 4, 5, 6, 7, 8):
        c[i] = (c[(i + 6) % 12] + 180.0) % 360.0
    return c


_PLACIDUS_SPEC = (
    # house index (0-based), fraction f, diurnal?
    (10, 1.0 / 3.0, True),    # cusp 11: H = SA_d/3
    (11, 2.0 / 3.0, True),    # cusp 12
    (1, 2.0 / 3.0, False),    # cusp 2:  H below horizon
    (2, 1.0 / 3.0, False),    # cusp 3
)


def _cusps_placidus(armc, eps_r, geolat, asc, mc):
    seed = _cusps_porphyry(asc, mc)
    c = [0.0] * 12
    c[0], c[9] = asc, mc
    for house, f, diurnal in _PLACIDUS_SPEC:
        lam = seed[house]
        for _ in range(80):
            dec = _dec_of_lon(lam, eps_r)
            ad = float(_ascensional_difference(geolat, dec))
            if diurnal:
                ra = armc + f * (90.0 + ad)
            else:
                ra = armc + 180.0 - f * (90.0 - ad)
            new = _ecl_point_at_ra(ra, eps_r)
            done = abs((new - lam + 180.0) % 360.0 - 180.0) < 1e-11
            lam = new
            if done:
                break
        c[house] = lam
    for i in (3, 4, 5, 6, 7, 8):
        c[i] = (c[(i + 6) % 12] + 180.0) % 360.0
    return c


def _mc_above_horizon(mc, armc, eps_r, geolat):
    """R/C convention (measured): inside the polar circles those two
    systems take the meridian∩ecliptic intersection ABOVE the horizon
    as cusp 10, while O/A/W/B keep the RA=θ point; for |φ| < 90−ε the
    RA=θ point is always above the horizon, so this never fires there
    (and P/K have already raised)."""
    zen, _, _ = _frame_vectors(armc, geolat)
    lam = np.radians(mc)
    mc_vec = np.array([np.cos(lam),
                       np.sin(lam) * np.cos(eps_r),
                       np.sin(lam) * np.sin(eps_r)])
    if np.dot(mc_vec, zen) < 0.0:
        return (mc + 180.0) % 360.0
    return mc


def cusps(armc: float, eps_deg: float, geolat: float,
          system: str = "P") -> tuple[float, ...]:
    """Cusps 1..12 (degrees) for a house-system letter (SE convention)."""
    eps_r = np.radians(eps_deg)
    if system in ("P", "K") and abs(geolat) >= 90.0 - eps_deg:
        # SE's uniform polar rule for Placidus/Koch (measured: it fails
        # at |lat| ≥ 90−ε even when the MC's own AD would exist)
        raise PolarHousesError(
            f"{system} houses undefined beyond the polar circle "
            f"(|lat| {abs(geolat):.4f} ≥ {90.0 - eps_deg:.4f})")
    ang = angles(armc, eps_deg, geolat)
    asc, mc = ang["ASC"], ang["MC"]
    if system in ("R", "C"):
        mc = _mc_above_horizon(mc, armc, eps_r, geolat)
    if system == "A" or system == "E":
        out = _cusps_equal(asc)
    elif system == "W":
        out = _cusps_whole(asc)
    elif system == "O":
        out = _cusps_porphyry(asc, mc)
    elif system == "R":
        out = _cusps_regiomontanus(armc, eps_r, geolat, asc, mc)
    elif system == "C":
        out = _cusps_campanus(armc, eps_r, geolat, asc, mc)
    elif system == "B":
        out = _cusps_alcabitius(armc, eps_r, geolat, asc, mc)
    elif system == "K":
        out = _cusps_koch(armc, eps_r, geolat, asc, mc)
    elif system == "P":
        out = _cusps_placidus(armc, eps_r, geolat, asc, mc)
    else:
        raise ValueError(f"unknown house system {system!r}")
    return tuple(out)
