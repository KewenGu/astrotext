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

from astrotext.kernel import timescales as ts  # noqa: E402

swe.set_ephe_path(str(ROOT / "data" / "ephe"))

JD0, JD1 = 2378497.0, 2597641.0  # 1800-01-01 .. 2399-12-31


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260708)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    lines = ["kernel-v2 verification vs SE 2.10.03 "
             f"(seed {args.seed})", "-" * 72]
    lines += k1_deltat(rng)
    lines += k1_utc(rng)
    lines += ["K1: PASS"]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
