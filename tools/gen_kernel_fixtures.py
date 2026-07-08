#!/usr/bin/env python3
"""Generate tests/kernel/fixtures/timescales.json — SE 2.10.03 truth values.

Black-box fixture set for the kernel-v2 time-scale module (KERNEL.md §5):
swe_utc_to_jd / swe_julday / swe_revjul / swe_deltat outputs on dates that
exercise every era and edge the engine supports.  Tests then run WITHOUT
Swiss Ephemeris: the kernel must reproduce these numbers.

Run on a machine with the vendored pyswisseph importable (macOS: vendor/lib).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "lib"))
import swisseph as swe  # noqa: E402

swe.set_ephe_path(str(ROOT / "data" / "ephe"))

OUT = ROOT / "tests" / "kernel" / "fixtures" / "timescales.json"

UTC_CASES = [
    # (y, m, d, h, mi, s) — era coverage + edges
    (1800, 1, 1, 0, 0, 0.0),
    (1820, 3, 4, 6, 0, 0.0),
    (1850, 12, 31, 23, 59, 59.5),
    (1900, 1, 1, 0, 0, 0.0),
    (1920, 7, 15, 12, 30, 15.25),
    (1941, 6, 22, 4, 0, 0.0),
    (1955, 1, 1, 0, 0, 0.0),          # tidal-adjustment boundary
    (1961, 8, 10, 18, 45, 30.0),
    (1971, 12, 31, 23, 59, 59.0),     # eve of UTC leap era
    (1972, 1, 1, 0, 0, 0.0),          # UTC leap era begins (dAT=10)
    (1972, 6, 30, 23, 59, 60.5),      # inside the first leap second
    (1972, 7, 1, 0, 0, 0.0),
    (1986, 5, 4, 6, 21, 0.0),
    (1994, 7, 29, 2, 30, 0.0),        # v1 UAT anchor (+0.74 s)
    (1999, 12, 31, 23, 59, 59.999999),
    (2000, 1, 1, 0, 0, 0.0),
    (2016, 12, 31, 23, 59, 60.0),     # most recent leap second
    (2017, 1, 1, 0, 0, 0.0),
    (2026, 7, 8, 12, 0, 0.0),
    (2033, 7, 1, 0, 0, 0.0),          # last leap-UTC-mode season (SE 2.10.03)
    (2033, 12, 31, 0, 0, 0.0),        # after the UT1-fallback flip
    (2050, 6, 1, 3, 33, 20.0),
    (2100, 2, 28, 23, 0, 0.0),
    (2200, 8, 8, 8, 8, 8.0),
    (2399, 12, 31, 12, 0, 0.0),
]

DELTAT_JDS = [
    2378497.0, 2385000.5, 2396758.25, 2405889.0, 2415020.5, 2420000.125,
    2430000.75, 2435108.5, 2440587.5, 2441317.5, 2444239.5, 2447892.5,
    2450814.5, 2451544.5, 2455197.5, 2457754.5, 2460000.0, 2461041.5,
    2469807.5, 2488069.5, 2506625.5, 2543317.5, 2561118.0, 2579853.5,
    2597641.0,
]

JULDAY_CASES = [
    # (y, m, d, hour_float, cal) — both calendars
    (1582, 10, 4, 12.0, "j"),
    (1582, 10, 15, 12.0, "g"),
    (1700, 2, 28, 6.5, "j"),
    (1799, 12, 31, 23.999, "g"),
    (1800, 2, 29, 0.0, "j"),          # Julian leap day, not Gregorian
    (1900, 1, 1, 0.0, "g"),
    (2000, 1, 1, 12.0, "g"),
    (2000, 1, 1, 12.0, "j"),
    (2100, 3, 1, 18.25, "g"),
    (2399, 12, 31, 0.0, "g"),
]


def main() -> None:
    out = {"se_version": swe.version, "utc_to_jd": [], "deltat": [],
           "julday": [], "revjul": []}
    for (y, m, d, h, mi, s) in UTC_CASES:
        tt, ut1 = swe.utc_to_jd(y, m, d, h, mi, s, swe.GREG_CAL)
        out["utc_to_jd"].append(
            {"utc": [y, m, d, h, mi, s], "jd_tt": tt, "jd_ut1": ut1})
    for j in DELTAT_JDS:
        out["deltat"].append({
            "jd_ut": j,
            "swieph_sec": swe.deltat_ex(j, swe.FLG_SWIEPH) * 86400.0,
            "jpleph_sec": swe.deltat_ex(j, swe.FLG_JPLEPH) * 86400.0,
        })
    for (y, m, d, h, cal) in JULDAY_CASES:
        c = swe.GREG_CAL if cal == "g" else swe.JUL_CAL
        j = swe.julday(y, m, d, h, c)
        out["julday"].append({"date": [y, m, d, h], "cal": cal, "jd": j})
        ry, rm, rd, rh = swe.revjul(j, c)
        out["revjul"].append({"jd": j, "cal": cal, "date": [ry, rm, rd, rh]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
