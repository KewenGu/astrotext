#!/usr/bin/env python3
"""Kernel-v2 verification vs Swiss Ephemeris — K-series acceptance report.

Needs the vendored pyswisseph (macOS: vendor/lib) for truth values, plus
jplephem/pyerfa for the kernel side.  Grows with the K-series: K1 today
(time scales), K2 planetary grid, ...

Usage: .venv/bin/python tools/verify_kernel.py [--seed N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor" / "lib"))

import swisseph as swe  # noqa: E402

from astrotext.kernel import bodies as kb  # noqa: E402
from astrotext.kernel import timescales as ts  # noqa: E402

swe.set_ephe_path(str(ROOT / "data" / "ephe"))

JD0, JD1 = 2378497.0, 2597641.0  # 1800-01-01 .. 2399-12-31

BODY_IPL = [("sun", 0), ("moon", 1), ("mercury", 2), ("venus", 3),
            ("mars", 4), ("jupiter", 5), ("saturn", 6), ("uranus", 7),
            ("neptune", 8), ("pluto", 9), ("chiron", 15)]

POINT_IPL = [("mean_node", 10), ("true_node", 11), ("mean_apogee", 12)]


def _wrap_asec(deg):
    return ((np.asarray(deg) + 180.0) % 360.0 - 180.0) * 3600.0


def k1_deltat(rng, n=20000) -> list[str]:
    jds = rng.uniform(JD0, JD1, n)
    fixture_jds = rng.uniform(2415020.5, 2469807.5, 200)   # 1900..2050 band
    out = []
    for name, flag in (("swieph", swe.FLG_SWIEPH), ("jpleph", swe.FLG_JPLEPH)):
        se = np.array([swe.deltat_ex(j, flag) for j in jds]) * 86400.0
        ours = ts.deltat_sec(jds, name)
        err = np.abs(ours - se)
        sef = np.array([swe.deltat_ex(j, flag) for j in fixture_jds]) * 86400.0
        ourf = ts.deltat_sec(fixture_jds, name)
        errf = np.abs(ourf - sef)
        out.append(
            f"ΔT[{name}]  span max|d|={err.max()*1e3:.3f} ms "
            f"(accept ≤50 ms)  fixture-band max|d|={errf.max()*1e3:.3f} ms "
            f"(accept ≤10 ms)  n={n}")
        assert err.max() <= 0.05 and errf.max() <= 0.01
    return out


def k1_utc(rng, n=5000) -> list[str]:
    worst_tt = worst_ut1 = 0.0
    for _ in range(n):
        jd = rng.uniform(JD0, JD1)
        y, m, d, h = swe.revjul(jd, swe.GREG_CAL)
        hh = int(h); mi = int((h - hh) * 60)
        s = round((h - hh) * 3600 - mi * 60, 3)
        if s >= 60.0:
            s = 59.999
        se_tt, se_ut1 = swe.utc_to_jd(y, m, d, hh, mi, s, swe.GREG_CAL)
        tt, ut1 = ts.utc_to_jd(y, m, d, hh, mi, s)
        worst_tt = max(worst_tt, abs(tt - se_tt))
        worst_ut1 = max(worst_ut1, abs(ut1 - se_ut1))
    out = [f"utc_to_jd  max|dTT|={worst_tt*86400*1e3:.4f} ms  "
           f"max|dUT1|={worst_ut1*86400*1e3:.4f} ms  (accept ≤10 ms)  n={n}"]
    assert worst_tt * 86400 <= 0.01 and worst_ut1 * 86400 <= 0.01
    return out


def k2_grid(rng, n_instants=65) -> list[str]:
    """K2 gate: 10 bodies × seeded instant grid vs swe_calc.

    Gates (KERNEL.md §9 + measured allowances, all documented):

    * lon/lat/RA/dec: planets ≤ 0.01″; Moon ≤ 0.01″ within 1850-2150 and
      ≤ 0.05″ (0.06″ RA) full-span — secular DE431(SE data)→DE440 lunar
      divergence.
    * dist: ≤ max(2e-8 au, 5e-9·r) — SE's compression error scales with
      distance (Pluto 1.1e-7 au = 2.8e-9 relative; Sun ~1 km absolute).
    * lon speed vs the TRUE derivative (5-pt numeric diff of SE's own
      apparent positions): planets ≤ 1.5e-6 °/day evaluated where the
      SE curve is stencil-smooth (its segment joints break the numeric
      reference, not our speed); measured planet residual is a uniform
      ~3e-7 °/day floor — SE's internally interpolated nutation rate.
      Moon ≤ 2e-5 °/day unfiltered: the DE431(SE data)→DE440 lunar
      divergence (~0.03″) rides on monthly-period terms, so its time-
      derivative contributes up to ~0.04″/day = 1.1e-5 °/day even
      mid-span (measured; 20× under the 1″/day display precision and
      ~0.2 s effect on exact-aspect times).
      Vs SE's REPORTED speed only loose bounds apply (planets 1.2e-5,
      Moon 1.2e-4 °/day): SE's speed polynomial deviates from the
      derivative of SE's own positions by up to ~0.18″/day for the Moon
      (measured; matches its documented speed precision), so exact
      parity there is neither achievable nor desirable."""
    jds = np.sort(rng.uniform(JD0, JD1, n_instants))
    fl = swe.FLG_SWIEPH | swe.FLG_SPEED
    out, fails = [], []
    core = (jds > 2396758.5) & (jds < 2506332.5)          # 1850..2150
    h = 0.01

    def se_lon(ipl, j):
        return swe.calc(float(j), ipl, fl)[0][0]

    def wrap_deg(d):
        return (d + 180.0) % 360.0 - 180.0

    for name, ipl in BODY_IPL:
        se = np.array([swe.calc(float(j), ipl, fl)[0] for j in jds])
        se_eq = np.array([swe.calc(float(j), ipl,
                                   fl | swe.FLG_EQUATORIAL)[0] for j in jds])
        # true derivative of SE's own apparent longitude (5-pt stencil);
        # a second stencil at 2h flags SE segment joints (C0 kinks).
        def stencil(j, hh):
            return (8.0 * wrap_deg(se_lon(ipl, j + hh) - se_lon(ipl, j - hh))
                    - wrap_deg(se_lon(ipl, j + 2 * hh)
                               - se_lon(ipl, j - 2 * hh))) / (12.0 * hh)

        se_num = np.array([stencil(j, h) for j in jds])
        se_num2 = np.array([stencil(j, 2 * h) for j in jds])
        smooth = np.abs(se_num - se_num2) <= 5e-7
        ours = kb.apparent_with_speed(name, jds)
        dlon = np.abs(_wrap_asec(ours.lon - se[:, 0]))
        dlat = np.abs((ours.lat - se[:, 1]) * 3600.0)
        ddist = np.abs(ours.dist - se[:, 2])
        dist_gate = np.maximum(2e-8, 5e-9 * se[:, 2])
        dls_all = np.abs(ours.lon_speed - se_num)
        dls_true = dls_all[smooth]
        dls_true_max = dls_true.max() if dls_true.size else 0.0
        if name == "moon":            # divergence-rate signal, unfiltered
            dls_true_max = dls_all.max()
        dls_rep = np.abs(ours.lon_speed - se[:, 3])
        dra = np.abs(_wrap_asec(ours.ra - se_eq[:, 0]))
        ddec = np.abs((ours.dec - se_eq[:, 1]) * 3600.0)
        if name == "moon":
            ok = (dlon.max() <= 0.05 and dlon[core].max() <= 0.01
                  and dlat.max() <= 0.05 and bool(np.all(ddist <= dist_gate))
                  and dls_true_max <= 2e-5 and dls_rep.max() <= 1.2e-4
                  and dra.max() <= 0.06 and ddec.max() <= 0.05)
        elif name == "chiron":
            # SE's Chiron (older JPL solution, seas file) vs our current
            # Horizons solution: an orbit-solution difference, not
            # pipeline error.  Oscillates with the 50-yr orbit (peaks
            # near perihelion passages): measured ≤1.02″ inside
            # 1880-2160, ~3.5″ at the span edges.  Display is 1″; ours
            # is the newer fit.  Gates: core ≤1.25″, full-span ≤5″.
            chi_core = (jds > 2407332.5) & (jds < 2509588.5)  # 1880..2160
            ok = (dlon[chi_core].max() <= 1.25 and dlon.max() <= 5.0
                  and dlat.max() <= 1.0 and ddist.max() <= 5e-5
                  and dls_true_max <= 2e-6 and dls_rep.max() <= 1.2e-5
                  and dra[chi_core].max() <= 1.25 and dra.max() <= 5.0
                  and ddec.max() <= 1.0)
        else:
            ok = (dlon.max() <= 0.01 and dlat.max() <= 0.01
                  and bool(np.all(ddist <= dist_gate))
                  and dls_true_max <= 1.5e-6 and dls_rep.max() <= 1.2e-5
                  and dra.max() <= 0.012 and ddec.max() <= 0.01)
        if not ok:
            fails.append(name)
        extra = ""
        if name == "chiron":
            extra = (f" [core dlon={dlon[chi_core].max():.3f}\" "
                     f"dra={dra[chi_core].max():.3f}\"]")
        out.append(
            f"{name:8} dlon={dlon.max():8.5f}\" dlat={dlat.max():8.5f}\" "
            f"ddist={ddist.max():.2e}au dspd_true={dls_true_max:.2e} "
            f"(n={int(smooth.sum())}/{len(jds)}) "
            f"dspd_rep={dls_rep.max():.2e}°/d dra={dra.max():8.5f}\" "
            f"ddec={ddec.max():8.5f}\" {'ok' if ok else 'FAIL'}{extra}")
    return out, fails


def k2_skyfield(rng, n=12) -> list[str]:
    """Third leg of the three-way check (§2): ours vs Skyfield (Rhodes),
    both reading the same DE440 excerpt.  Independent reduction code —
    agreement here isolates pipeline correctness from SE model/data
    differences.  Moon residual ~1.3 mas = the TDB−TT term Skyfield
    applies and we document as negligible (§4 note).  Optional: skipped
    when Skyfield isn't importable (it is dev-only)."""
    try:
        from skyfield.api import load
        from skyfield.framelib import ecliptic_frame
    except ImportError:
        return ["skyfield: not installed — three-way check skipped"]
    tsky = load.timescale()
    eph = load(str(ROOT / "data" / "kernel" / "de440_1799_2400.bsp"))
    earth = eph["earth"]
    targets = {"sun": eph["sun"], "moon": eph["moon"],
               "mars": eph["mars barycenter"],
               "venus": eph["venus"], "pluto": eph["pluto barycenter"]}
    jds = np.sort(rng.uniform(JD0 + 100, JD1 - 100, n))
    out = []
    for name, t in targets.items():
        wl = wb = 0.0
        for jd in jds:
            app = earth.at(tsky.tt_jd(float(jd))).observe(t).apparent()
            lat, lon, _ = app.frame_latlon(ecliptic_frame)
            a = kb.apparent(name, float(jd))
            wl = max(wl, abs(_wrap_asec(a.lon - lon.degrees)))
            wb = max(wb, abs((a.lat - lat.degrees) * 3600.0))
        gate = 0.01 if name != "moon" else 0.01
        out.append(f"skyfield {name:6} dlon={wl:.5f}\" dlat={wb:.5f}\" "
                   f"{'ok' if wl <= gate and wb <= gate else 'FAIL'}")
        assert wl <= gate and wb <= gate
    return out


def k3_points(rng, n_instants=65) -> tuple[list[str], list[str]]:
    """K3 gate: lunar nodes + mean apogee vs swe_calc.

    * true_node: osculating node from DE440 states — ≤0.04″ inside
      1850-2150, ≤0.10″ full-span: the node amplifies the lunar
      DE431→DE440 plane divergence by ~1/sin i ≈ 11 (measured 0.025″
      core / 0.058″ full); same for its speed (≤1e-4 °/day, shifting
      node stations by minutes at most).  dist (osculating-ellipse
      radius at the node, μ = GM_E+GM_Moon, DE440 header) ≤2e-9 au.
    * mean_node: Meeus/ELP polynomial + Δψ vs SE's Moshier fit with
      DE431-derived corrections — ≤0.6″ (measured drift reaches 0.52″
      at 2399; SE manual §2.2.1 estimates its own mean points at ~1″).
    * mean_apogee: same source + inclined-orbit projection — ≤2″ lon,
      ≤0.3″ lat.  Display precision is 1″; the engine's mean points are
      astrological constructs with several published variants.
    """
    from astrotext.kernel import points as kp
    jds = np.sort(rng.uniform(JD0, JD1, n_instants))
    fl = swe.FLG_SWIEPH | swe.FLG_SPEED
    core = (jds > 2396758.5) & (jds < 2506332.5)
    out, fails = [], []
    gates = {
        "true_node": dict(lon=0.10, lon_core=0.04, lat=1e-9, dist=2e-9,
                          spd=1e-4),
        "mean_node": dict(lon=0.8, lon_core=0.6, lat=1e-9, dist=1e-9,
                          spd=1e-5),
        "mean_apogee": dict(lon=2.0, lon_core=2.0, lat=0.3, dist=1e-9,
                            spd=1e-5),
    }
    for name, ipl in POINT_IPL:
        se = np.array([swe.calc(float(j), ipl, fl)[0] for j in jds])
        ours = kp.apparent_with_speed(name, jds)
        g = gates[name]
        dlon = np.abs(_wrap_asec(ours.lon - se[:, 0]))
        dlat = np.abs((ours.lat - se[:, 1]) * 3600.0)
        ddist = np.abs(ours.dist - se[:, 2])
        dspd = np.abs(ours.lon_speed - se[:, 3])
        # lat gate in arcsec for the apogee; nodes are exactly 0 both sides
        ok = (dlon.max() <= g["lon"] and dlon[core].max() <= g["lon_core"]
              and (dlat.max() <= g["lat"] if name == "mean_apogee"
                   else dlat.max() == 0.0)
              and ddist.max() <= g["dist"] and dspd.max() <= g["spd"])
        if not ok:
            fails.append(name)
        out.append(
            f"{name:12} dlon={dlon.max():7.4f}\" (core {dlon[core].max():7.4f}\") "
            f"dlat={dlat.max():7.4f}\" ddist={ddist.max():.2e}au "
            f"dspd={dspd.max():.2e}°/d {'ok' if ok else 'FAIL'}")
    return out, fails


def k4_houses(rng, n_configs=40) -> tuple[list[str], list[str]]:
    """K4 gate: 8 systems + angles vs swe_houses_armc at identical
    (armc, eps, lat) — pure formula parity, ≤0.001″ (KERNEL.md §7).
    The ARMC time-chain (gst06a vs SE sidtime) is gated separately at
    ≤0.02″ ≈ 1.3 ms of time — the K1/K2 frame-model gap."""
    from astrotext.kernel import houses as kh
    from astrotext.kernel import timescales as kts
    lats = (0.0, 31.911, -31.911, 48.4, -48.4, 59.93, -59.93, 66.99, -66.99)
    out, fails = [], []
    worst = {s: 0.0 for s in kh.SYSTEMS}
    worst_ang = 0.0
    n_polar = 0
    for _ in range(n_configs):
        armc = rng.uniform(0.0, 360.0)
        eps = rng.uniform(23.42, 23.46)
        for lat in lats:
            se_c = se_a = None
            for sysl in kh.SYSTEMS:
                se_fail = ours_fail = False
                try:
                    se_c, se_a = swe.houses_armc(armc, lat, eps,
                                                 sysl.encode())
                except Exception:
                    se_fail = True
                try:
                    ours = kh.cusps(armc, eps, lat, sysl)
                except kh.PolarHousesError:
                    ours_fail = True
                if se_fail or ours_fail:
                    if se_fail != ours_fail:
                        fails.append(f"{sysl}@lat{lat}: polar mismatch "
                                     f"(se_fail={se_fail})")
                    else:
                        n_polar += 1
                    continue
                d = max(abs(_wrap_asec(ours[i] - se_c[i])) for i in range(12))
                worst[sysl] = max(worst[sysl], d)
                ang = kh.angles(armc, eps, lat)
                for i, k in ((0, "ASC"), (1, "MC"), (2, "ARMC"),
                             (3, "VERTEX"), (4, "EQUATORIAL_ASC")):
                    ref = ang[k]
                    if k == "MC" and sysl in ("R", "C"):
                        ref = ours[9]      # R/C report the flipped MC
                    worst_ang = max(worst_ang,
                                    abs(_wrap_asec(ref - se_a[i])))
    for sysl in kh.SYSTEMS:
        if worst[sysl] > 0.001:
            fails.append(f"{sysl}: {worst[sysl]:.6f}\"")
    if worst_ang > 0.001:
        fails.append(f"angles: {worst_ang:.6f}\"")
    out.append("houses formula parity (vs swe_houses_armc, "
               f"{n_configs} configs × {len(lats)} lats): " +
               " ".join(f"{s}={worst[s]:.6f}\"" for s in kh.SYSTEMS))
    out.append(f"angles ≤{worst_ang:.6f}\"  (gate 0.001\"); "
               f"polar-raise agreement on {n_polar} configs")
    # --- ARMC time chain: gst06a vs SE sidtime ------------------------
    # SE's long-term sidereal-time splice deviates from IAU-2006 GST by
    # −0.36″@1800 … +1.79″@2100 … −8.5″@2399, ~0 only in its calibrated
    # 1900-2050 era.  Ours matches Skyfield's independent IAU
    # implementation to ≤0.0005″ across the full span (three-way, see
    # KERNEL.md status) — the deviation is SE's, so the tight gate
    # applies to the modern window and a loose documented one outside.
    worst_mod = worst_all = 0.0
    for _ in range(300):
        jd_ut = rng.uniform(JD0, JD1)
        lon = rng.uniform(-180.0, 180.0)
        se_c, se_a = swe.houses_ex(jd_ut, 10.0, lon, b"O", 0)
        jd_tt = kts.ut1_to_tt(jd_ut, "swieph")
        ours = kh.armc_deg(jd_ut, jd_tt, lon)
        d = abs(_wrap_asec(ours - se_a[2]))
        worst_all = max(worst_all, d)
        if 2410000.0 < jd_ut < 2469807.5:      # ~1886..2050
            worst_mod = max(worst_mod, d)
    out.append(f"ARMC time-chain vs SE: 1886-2050 max|d|={worst_mod:.5f}\" "
               f"(gate 0.02\"); full-span {worst_all:.3f}\" (gate 10\", "
               f"SE's long-term sidtime splice — ours ≡ Skyfield ≤0.0005\")")
    if worst_mod > 0.02 or worst_all > 10.0:
        fails.append(f"armc chain: mod {worst_mod:.5f}\" all {worst_all:.3f}\"")
    return out, fails


def k5_sidereal(rng, n_instants=40) -> tuple[list[str], list[str]]:
    """K5 gate: ayanamsas + native-sidereal parity (KERNEL.md §8).

    * ayanamsa (both flavours) vs swe_get_ayanamsa_ex: ≤0.01″ — the
      IAU-2006 p_A accumulation reproduces SE's traditional algorithm
      at ≤0.002″ (measured).
    * end-to-end sidereal longitudes (our apparent lon − ayanamsa_true)
      vs swe_calc FLG_SIDEREAL: planets ≤0.015″ (tropical parity 0.0074
      + ayanamsa 0.002); Moon ≤0.06″ full-span (the K2 lunar DE
      divergence rides on top unchanged)."""
    from astrotext.kernel import sidereal as ks
    sid_ids = {"fagan_bradley": swe.SIDM_FAGAN_BRADLEY,
               "lahiri": swe.SIDM_LAHIRI, "raman": swe.SIDM_RAMAN,
               "krishnamurti": swe.SIDM_KRISHNAMURTI}
    jds = np.sort(rng.uniform(JD0, JD1, n_instants))
    out, fails = [], []
    for mode, sid in sid_ids.items():
        swe.set_sid_mode(sid, 0, 0)
        wt = wm = 0.0
        for j in jds:
            rt = swe.get_ayanamsa_ex(float(j), swe.FLG_SWIEPH)
            rn = swe.get_ayanamsa_ex(float(j),
                                     swe.FLG_SWIEPH | swe.FLG_NONUT)
            se_t = rt[1] if isinstance(rt, tuple) else rt
            se_n = rn[1] if isinstance(rn, tuple) else rn
            wt = max(wt, abs(_wrap_asec(ks.ayanamsa_deg(float(j), mode, True)
                                        - se_t)))
            wm = max(wm, abs(_wrap_asec(ks.ayanamsa_deg(float(j), mode, False)
                                        - se_n)))
        wsid = {}
        for name, ipl in (("sun", 0), ("moon", 1), ("saturn", 6)):
            se_sid = np.array([swe.calc(float(j), ipl,
                                        swe.FLG_SWIEPH | swe.FLG_SIDEREAL
                                        )[0][0] for j in jds])
            ours = kb.apparent(name, jds)
            our_sid = ks.sidereal_lon(ours.lon, jds, mode)
            wsid[name] = np.max(np.abs(_wrap_asec(our_sid - se_sid)))
        ok = (wt <= 0.01 and wm <= 0.01 and wsid["sun"] <= 0.015
              and wsid["saturn"] <= 0.015 and wsid["moon"] <= 0.06)
        if not ok:
            fails.append(mode)
        out.append(f"{mode:14} d_ay(true)={wt:.4f}\" d_ay(mean)={wm:.4f}\" "
                   f"sid: sun={wsid['sun']:.4f}\" moon={wsid['moon']:.4f}\" "
                   f"saturn={wsid['saturn']:.4f}\" {'ok' if ok else 'FAIL'}")
    return out, fails


def k6_observing(rng, n_star_jds=12, n_rise=30) -> tuple[list[str], list[str]]:
    """K6 gate.

    * fixed stars vs swe_fixstar: ≤0.2″ within 1850-2150, ≤0.8″
      full-span.  The residual is zero at the catalog epoch and grows
      ∝ pm·|t−epoch| (Altair 0.62″, Sirius 0.47″ at 2399) — sefstars'
      older Hipparcos-1997 proper motions vs our van Leeuwen 2007;
      ours matches Skyfield on the same catalog rows to 0.0001″ even at
      the span edges, so the gap is SE-side (measured).  Display 1″,
      conjunction orb 1°.
    * sun rise/set ≤1 s vs swe_rise_trans (default flags = engine
      usage; the −0.61233° effective horizon is black-box-calibrated,
      see kernel/observing.py)."""
    from astrotext.kernel import observing as ko
    out, fails = [], []
    jds = np.sort(rng.uniform(JD0 + 200, JD1 - 200, n_star_jds))
    core = (jds > 2396758.5) & (jds < 2506332.5)
    worst_star, worst_name, worst_core = 0.0, "", 0.0
    for name in ko.STAR_NAMES:
        se = np.array([swe.fixstar(name, float(j),
                                   swe.FLG_SWIEPH)[0][:2] for j in jds])
        ours = ko.star_apparent(name, jds)
        dd = np.hypot(_wrap_asec(ours.lon - se[:, 0]),
                      (ours.lat - se[:, 1]) * 3600.0)
        worst_core = max(worst_core, float(dd[core].max()))
        if float(dd.max()) > worst_star:
            worst_star, worst_name = float(dd.max()), name
    ok_star = worst_star <= 0.8 and worst_core <= 0.2
    out.append(f"fixed stars (22, {n_star_jds} instants): worst "
               f"{worst_star:.3f}\" ({worst_name}), core {worst_core:.3f}\" "
               f"(gates 0.8/0.2\") {'ok' if ok_star else 'FAIL'}")
    if not ok_star:
        fails.append(f"stars: {worst_name} {worst_star:.3f}\"")
    worst_rs = 0.0
    n_polar_agree = 0
    for _ in range(n_rise):
        jd = rng.uniform(JD0 + 200, JD1 - 200)
        lat = rng.uniform(-65.0, 65.0)
        lon = rng.uniform(-180.0, 180.0)
        for kind, rsmi in (("rise", swe.CALC_RISE), ("set", swe.CALC_SET)):
            try:
                ret, tret = swe.rise_trans(jd, swe.SUN, rsmi,
                                           (lon, lat, 0.0))
                se_t = tret[0] if ret == 0 else None
            except Exception:
                se_t = None
            our_t = ko.next_sun_event(jd, lat, lon, kind)
            if se_t is None or our_t is None:
                n_polar_agree += int((se_t is None) == (our_t is None))
                continue
            worst_rs = max(worst_rs, abs(our_t - se_t) * 86400.0)
    ok_rs = worst_rs <= 1.0
    out.append(f"sun rise/set ({n_rise} configs): worst |dt| = "
               f"{worst_rs:.3f} s  gate 1 s {'ok' if ok_rs else 'FAIL'}")
    if not ok_rs:
        fails.append(f"rise/set: {worst_rs:.3f} s")
    return out, fails


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260708)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    lines = ["kernel-v2 verification vs SE 2.10.03 "
             f"(seed {args.seed})", "-" * 72]
    lines += k1_deltat(rng)
    lines += k1_utc(rng)
    lines += ["K1: PASS", ""]
    k2_lines, k2_fails = k2_grid(rng)
    lines += k2_lines
    lines += k2_skyfield(rng)
    lines += [f"K2: {'PASS' if not k2_fails else 'FAIL ' + str(k2_fails)}", ""]
    k3_lines, k3_fails = k3_points(rng)
    lines += k3_lines
    lines += [f"K3: {'PASS' if not k3_fails else 'FAIL ' + str(k3_fails)}", ""]
    k4_lines, k4_fails = k4_houses(rng)
    lines += k4_lines
    lines += [f"K4: {'PASS' if not k4_fails else 'FAIL ' + str(k4_fails)}", ""]
    k5_lines, k5_fails = k5_sidereal(rng)
    lines += k5_lines
    lines += [f"K5: {'PASS' if not k5_fails else 'FAIL ' + str(k5_fails)}", ""]
    k6_lines, k6_fails = k6_observing(rng)
    lines += k6_lines
    lines += [f"K6: {'PASS' if not k6_fails else 'FAIL ' + str(k6_fails)}"]
    print("\n".join(lines))
    if k2_fails or k3_fails or k4_fails or k5_fails or k6_fails:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
