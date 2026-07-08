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
            ("neptune", 8), ("pluto", 9)]


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
        else:
            ok = (dlon.max() <= 0.01 and dlat.max() <= 0.01
                  and bool(np.all(ddist <= dist_gate))
                  and dls_true_max <= 1.5e-6 and dls_rep.max() <= 1.2e-5
                  and dra.max() <= 0.012 and ddec.max() <= 0.01)
        if not ok:
            fails.append(name)
        out.append(
            f"{name:8} dlon={dlon.max():8.5f}\" dlat={dlat.max():8.5f}\" "
            f"ddist={ddist.max():.2e}au dspd_true={dls_true_max:.2e} "
            f"(n={int(smooth.sum())}/{len(jds)}) "
            f"dspd_rep={dls_rep.max():.2e}°/d dra={dra.max():8.5f}\" "
            f"ddec={ddec.max():8.5f}\" {'ok' if ok else 'FAIL'}")
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
    lines += [f"K2: {'PASS' if not k2_fails else 'FAIL ' + str(k2_fails)}"]
    print("\n".join(lines))
    if k2_fails:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
