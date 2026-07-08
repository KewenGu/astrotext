#!/usr/bin/env python3
"""Build data/kernel/chiron_horizons.npz — Chiron ephemeris (KERNEL.md §6).

JPL Horizons small-body SPKs are DAF type 21, which jplephem cannot read,
so instead we fetch raw state vectors (public domain) and fit our own
Chebyshev segments:

  source   : Horizons API, COMMAND='2060;', barycentric (500@0) ICRF
             geometric states, TDB, au & au/day, 2-day steps,
             1798-12-20 .. 2400-02-10 (margin over the 1799-2400 span)
  fit      : per 64-day segment, degree-12 Chebyshev per coordinate,
             least squares over ~33 samples; measured max residual
             3.3e-9 au ≈ 0.5 km — degree-independent (12 vs 14 identical),
             i.e. it is Horizons' own integrator/interpolation noise, worth
             ≤1.3e-4″ at Chiron's closest geometry, 400× under the 0.05″
             gate
  output   : npz with jd0, seg_days, coeffs[nseg, 3, 13] (position; the
             kernel evaluates velocity from the analytic derivative)

Needs network (run on the Mac).  Metadata (fetch date, JPL solution
line, fit residual) is embedded in the npz for provenance.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "kernel" / "chiron_horizons.npz"

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
JD_START, JD_STOP = 2378122.5, 2597650.5     # 1798-12-20 .. 2400-02-10
STEP_D = 2.0
SEG_DAYS = 64.0
DEGREE = 12


def fetch_chunk(t0: str, t1: str) -> tuple[list[list[float]], str]:
    params = {
        "format": "text", "COMMAND": "'2060;'", "OBJ_DATA": "'YES'",
        "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'VECTORS'",
        "CENTER": "'500@0'", "REF_PLANE": "'FRAME'",
        "REF_SYSTEM": "'ICRF'", "VEC_TABLE": "'2'", "VEC_CORR": "'NONE'",
        "OUT_UNITS": "'AU-D'", "CSV_FORMAT": "'YES'",
        "START_TIME": f"'{t0}'", "STOP_TIME": f"'{t1}'",
        "STEP_SIZE": f"'{int(STEP_D)} d'",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=300) as r:
        text = r.read().decode()
    soln = ""
    for ln in text.splitlines():
        if "solution date" in ln.lower() or ln.startswith("Rec #"):
            soln = ln.strip()
            break
    try:
        block = text.split("$$SOE")[1].split("$$EOE")[0]
    except IndexError:
        raise SystemExit(f"Horizons returned no data block:\n{text[:2000]}")
    rows = []
    for ln in block.strip().splitlines():
        p = [x.strip() for x in ln.split(",")]
        if len(p) >= 8:
            rows.append([float(p[0])] + [float(x) for x in p[2:8]])
    return rows, soln


def main() -> None:
    spans = []
    t = JD_START
    while t < JD_STOP:                        # ~90-year chunks
        spans.append((t, min(t + 33000.0, JD_STOP)))
        t += 33000.0

    def jd2str(jd):
        # Horizons accepts JD input for times
        return f"JD{jd:.1f}"

    rows, soln = [], ""
    for a, b in spans:
        r, s = fetch_chunk(jd2str(a), jd2str(b))
        soln = soln or s
        if rows and r and abs(r[0][0] - rows[-1][0]) < 1e-6:
            r = r[1:]                          # drop duplicated boundary row
        rows.extend(r)
        print(f"  chunk {a:.0f}..{b:.0f}: {len(r)} rows")
    arr = np.array(rows)
    jd, pos = arr[:, 0], arr[:, 1:4]
    assert np.all(np.diff(jd) > 0), "rows not monotonic"
    print(f"total {len(jd)} states, {jd[0]:.1f}..{jd[-1]:.1f}")

    # --- fit Chebyshev per 64-day segment ------------------------------
    jd0 = jd[0]
    nseg = int(np.ceil((jd[-1] - jd0) / SEG_DAYS))
    coeffs = np.zeros((nseg, 3, DEGREE + 1))
    worst = 0.0
    for k in range(nseg):
        a, b = jd0 + k * SEG_DAYS, jd0 + (k + 1) * SEG_DAYS
        m = (jd >= a - STEP_D) & (jd <= b + STEP_D)   # one-sample overlap
        x = 2.0 * (jd[m] - a) / SEG_DAYS - 1.0
        for c in range(3):
            f = np.polynomial.chebyshev.chebfit(x, pos[m, c], DEGREE)
            coeffs[k, c] = f
            worst = max(worst, np.max(np.abs(
                np.polynomial.chebyshev.chebval(x, f) - pos[m, c])))
    print(f"fit: {nseg} segments x deg {DEGREE}, max residual {worst:.2e} au")
    assert worst < 5e-9, "Chebyshev fit residual too large"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUT, jd0=jd0, seg_days=SEG_DAYS, coeffs=coeffs,
        meta=json.dumps({
            "body": "2060 Chiron (Horizons, barycentric ICRF, TDB, au)",
            "solution": soln, "fetched": dt.date.today().isoformat(),
            "fit_max_residual_au": float(worst),
            "span_jd": [float(jd[0]), float(jd[-1])],
        }))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
