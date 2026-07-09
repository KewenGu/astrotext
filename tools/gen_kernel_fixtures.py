#!/usr/bin/env python3
"""Generate tests/kernel/fixtures/*.json — SE 2.10.03 truth values.

Black-box fixtures for the kernel-v2 modules (KERNEL.md §5, §11):

* timescales.json — swe_utc_to_jd / swe_julday / swe_revjul / swe_deltat
  on dates that exercise every era and edge the engine supports.
* bodies.json — swe_calc (SWIEPH|SPEED, plus EQUATORIAL) for the ten
  §4 bodies on a seeded instant grid spanning 1800-2399.

Tests then run WITHOUT Swiss Ephemeris: the kernel must reproduce these.
Run on a machine with the vendored pyswisseph importable (macOS: vendor/lib).
"""
import json
import sys
from pathlib import Path

import numpy as np

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


BODY_IPL = [("sun", 0), ("moon", 1), ("mercury", 2), ("venus", 3),
            ("mars", 4), ("jupiter", 5), ("saturn", 6), ("uranus", 7),
            ("neptune", 8), ("pluto", 9), ("chiron", 15)]

POINT_IPL = [("mean_node", 10), ("true_node", 11), ("mean_apogee", 12)]


def _calc_case(name, ipl, jd, fl):
    ecl, _ = swe.calc(float(jd), ipl, fl)
    equ, _ = swe.calc(float(jd), ipl, fl | swe.FLG_EQUATORIAL)
    return {
        "body": name, "jd_tt": float(jd),
        "lon": ecl[0], "lat": ecl[1], "dist": ecl[2],
        "lon_speed": ecl[3], "lat_speed": ecl[4],
        "dist_speed": ecl[5], "ra": equ[0], "dec": equ[1],
    }


def gen_bodies() -> None:
    rng = np.random.default_rng(42)
    jds = np.sort(rng.uniform(2378497.0, 2597641.0, 20))   # 1800..2399 TT
    fl = swe.FLG_SWIEPH | swe.FLG_SPEED
    cases = [_calc_case(name, ipl, jd, fl)
             for jd in jds for name, ipl in BODY_IPL]
    out = ROOT / "tests" / "kernel" / "fixtures" / "bodies.json"
    out.write_text(json.dumps(
        {"se_version": swe.version, "flags": "SWIEPH|SPEED", "cases": cases},
        indent=1))
    print(f"wrote {out} ({len(cases)} cases)")
    cases = [_calc_case(name, ipl, jd, fl)
             for jd in jds for name, ipl in POINT_IPL]
    out = ROOT / "tests" / "kernel" / "fixtures" / "points.json"
    out.write_text(json.dumps(
        {"se_version": swe.version, "flags": "SWIEPH|SPEED", "cases": cases},
        indent=1))
    print(f"wrote {out} ({len(cases)} cases)")


HOUSE_SYSTEMS = ("P", "K", "O", "R", "C", "A", "W", "B")


def gen_houses() -> None:
    rng = np.random.default_rng(4242)
    cases = []
    lats = (0.0, 31.911, -48.4, 59.93, -59.93, 66.99, -66.99)
    for _ in range(6):
        armc = float(rng.uniform(0.0, 360.0))
        eps = float(rng.uniform(23.42, 23.46))
        for lat in lats:
            for s in HOUSE_SYSTEMS:
                try:
                    c, a = swe.houses_armc(armc, lat, eps, s.encode())
                    cases.append({"armc": armc, "eps": eps, "lat": lat,
                                  "system": s, "cusps": list(c),
                                  "asc": a[0], "mc": a[1], "vertex": a[3],
                                  "eq_asc": a[4]})
                except Exception:
                    cases.append({"armc": armc, "eps": eps, "lat": lat,
                                  "system": s, "raises": True})
    chain = []
    for _ in range(8):
        jd_ut = float(rng.uniform(2378497.0, 2597641.0))
        lon = float(rng.uniform(-180.0, 180.0))
        c, a = swe.houses_ex(jd_ut, 10.0, lon, b"O", 0)
        chain.append({"jd_ut": jd_ut, "lon": lon, "armc": a[2]})
    out = ROOT / "tests" / "kernel" / "fixtures" / "houses.json"
    out.write_text(json.dumps(
        {"se_version": swe.version, "cases": cases, "armc_chain": chain},
        indent=1))
    print(f"wrote {out} ({len(cases)} cases + {len(chain)} chain)")


SID_MODES = {"fagan_bradley": 0, "lahiri": 1, "raman": 3, "krishnamurti": 5}


def gen_sidereal() -> None:
    rng = np.random.default_rng(77)
    jds = np.sort(rng.uniform(2378497.0, 2597641.0, 14))
    ay_cases, sid_cases = [], []
    for mode, sid in SID_MODES.items():
        swe.set_sid_mode(sid, 0, 0)
        for jd in jds:
            rt = swe.get_ayanamsa_ex(float(jd), swe.FLG_SWIEPH)
            rn = swe.get_ayanamsa_ex(float(jd),
                                     swe.FLG_SWIEPH | swe.FLG_NONUT)
            ay_cases.append({
                "mode": mode, "jd_tt": float(jd),
                "true": rt[1] if isinstance(rt, tuple) else rt,
                "mean": rn[1] if isinstance(rn, tuple) else rn})
        for jd in jds[::2]:
            for name, ipl in (("sun", 0), ("moon", 1), ("saturn", 6)):
                lon = swe.calc(float(jd), ipl,
                               swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
                sid_cases.append({"mode": mode, "body": name,
                                  "jd_tt": float(jd), "lon": lon})
    out = ROOT / "tests" / "kernel" / "fixtures" / "sidereal.json"
    out.write_text(json.dumps(
        {"se_version": swe.version, "ayanamsa": ay_cases,
         "sidereal_lon": sid_cases}, indent=1))
    print(f"wrote {out} ({len(ay_cases)}+{len(sid_cases)} cases)")


def gen_observing() -> None:
    rng = np.random.default_rng(99)
    star_jds = np.sort(rng.uniform(2378700.0, 2597400.0, 6))
    star_cases = []
    names = json.loads(
        (ROOT / "data" / "kernel" / "hipparcos_22.json").read_text())["stars"]
    for name in names:
        for jd in star_jds:
            xx = swe.fixstar(name, float(jd), swe.FLG_SWIEPH)[0]
            star_cases.append({"star": name, "jd_tt": float(jd),
                               "lon": xx[0], "lat": xx[1]})
    rise_cases = []
    for _ in range(12):
        jd = float(rng.uniform(2378700.0, 2597400.0))
        lat = float(rng.uniform(-65.0, 65.0))
        lon = float(rng.uniform(-180.0, 180.0))
        for kind, rsmi in (("rise", swe.CALC_RISE), ("set", swe.CALC_SET)):
            ret, tret = swe.rise_trans(jd, swe.SUN, rsmi, (lon, lat, 0.0))
            if ret == 0:
                rise_cases.append({"jd_ut": jd, "lat": lat, "lon": lon,
                                   "kind": kind, "t": tret[0]})
    out = ROOT / "tests" / "kernel" / "fixtures" / "observing.json"
    out.write_text(json.dumps(
        {"se_version": swe.version, "stars": star_cases,
         "rise_set": rise_cases}, indent=1))
    print(f"wrote {out} ({len(star_cases)}+{len(rise_cases)} cases)")


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
    gen_bodies()
    gen_houses()
    gen_sidereal()
    gen_observing()


if __name__ == "__main__":
    main()
