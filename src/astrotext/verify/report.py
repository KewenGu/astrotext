"""Verification report generator (`make verify`).

Compares the Python engine against the independently-driven swetest reference
CLI over a deterministic sample grid, runs the timezone acceptance cases, and
writes ``verification_report.md`` at the repo root.  Exit code 0 only if every
check passes — this is the M-milestone acceptance gate.
"""
from __future__ import annotations

import datetime as dt
import random
import sys

import swisseph as swe

from .. import __version__, config
from ..core.angles import angdiff
from ..ephem import SE_POINTS, Ephemeris
from ..timespace import NonexistentLocalTime, Place, resolve
from . import swetest_ref

# tolerances, degrees.  swetest prints 7 decimals => 5e-8 quantization.
TOL_LON = 2e-7   # 0.00072 arcsec
TOL_LAT = 2e-7
TOL_SPEED = 2e-7
TOL_CUSP = 2e-7

LOCATIONS = [
    ("Beijing", 39.9042, 116.4074),
    ("Reykjavik", 64.1466, -21.9426),
    ("Sydney", -33.8688, 151.2093),
    ("Quito", -0.1807, -78.4678),
]
HOUSE_SYSTEMS = ["P", "W"]

SEED = 20260708
N_RANDOM_JDS = 60


def _jd_grid() -> list[float]:
    rng = random.Random(SEED)
    lo = swe.julday(1800, 1, 5, 0.0)
    hi = swe.julday(2399, 12, 25, 0.0)
    jds = [swe.julday(2000, 1, 1, 12.0), lo + 0.25, hi - 0.25,
           swe.julday(1900, 6, 15, 6.5), swe.julday(2100, 1, 1, 18.0)]
    jds += [rng.uniform(lo, hi) for _ in range(N_RANDOM_JDS)]
    return jds


def compare_positions(eph: Ephemeris, jds: list[float]) -> dict[str, dict[str, float]]:
    """max |Δ| per point across the grid, vs swetest."""
    worst: dict[str, dict[str, float]] = {
        k: {"lon": 0.0, "lat": 0.0, "speed": 0.0} for k in swetest_ref.NAME_TO_KEY.values()
    }
    for jd in jds:
        ref = swetest_ref.positions(jd)
        for key, (rlon, rlat, rspeed) in ref.items():
            st = eph.state(jd, key)
            w = worst[key]
            w["lon"] = max(w["lon"], abs(angdiff(st.lon, rlon)))
            w["lat"] = max(w["lat"], abs(st.lat - rlat))
            w["speed"] = max(w["speed"], abs(st.lon_speed - rspeed))
    return worst


def compare_houses(eph: Ephemeris, jds: list[float]) -> dict[str, float]:
    """max |Δ| for cusps and angles across grid x locations x systems."""
    worst = {"cusp": 0.0, "ASC": 0.0, "MC": 0.0, "ARMC": 0.0, "VERTEX": 0.0}
    for jd in jds[:20]:  # houses are cheap but swetest calls dominate; 20 moments suffice
        for _, lat, lon in LOCATIONS:
            for hsys in HOUSE_SYSTEMS:
                rcusps, rnamed = swetest_ref.houses(jd, lon, lat, hsys)
                cusps, named = eph.houses(jd, lat, lon, hsys)
                for a, b in zip(cusps, rcusps):
                    worst["cusp"] = max(worst["cusp"], abs(angdiff(a, b)))
                for k in ("ASC", "MC", "ARMC", "VERTEX"):
                    worst[k] = max(worst[k], abs(angdiff(named[k], rnamed[k])))
    return worst


def timespace_cases() -> list[tuple[str, str, str, bool]]:
    """(case, got, expected, ok) rows — the China-history acceptance set."""
    rows: list[tuple[str, str, str, bool]] = []
    beijing = Place(lat=39.9042, lon=116.4074, name="Beijing", tz="Asia/Shanghai")

    def add(desc: str, got: str, exp: str) -> None:
        rows.append((desc, got, exp, got == exp))

    m = resolve(dt.datetime(1988, 6, 15, 14, 30), beijing)
    add("1988-06-15 14:30 Beijing (summer, DST era)",
        m.utc.strftime("%Y-%m-%d %H:%M UTC"), "1988-06-15 05:30 UTC")

    m = resolve(dt.datetime(1988, 1, 15, 14, 30), beijing)
    add("1988-01-15 14:30 Beijing (winter, DST era)",
        m.utc.strftime("%Y-%m-%d %H:%M UTC"), "1988-01-15 06:30 UTC")

    try:
        resolve(dt.datetime(1986, 5, 4, 2, 30), beijing)
        add("1986-05-04 02:30 Beijing (DST gap)", "no error", "NonexistentLocalTime")
    except NonexistentLocalTime:
        add("1986-05-04 02:30 Beijing (DST gap)", "NonexistentLocalTime", "NonexistentLocalTime")

    m0 = resolve(dt.datetime(1986, 9, 14, 1, 30), beijing, fold=0)
    m1 = resolve(dt.datetime(1986, 9, 14, 1, 30), beijing, fold=1)
    amb = any(f.startswith("ambiguous") for f in m0.flags)
    add("1986-09-14 01:30 Beijing (ambiguous, fold=0)",
        m0.utc.strftime("%H:%M") + (" +flag" if amb else " -flag"), "16:30 +flag")
    add("1986-09-14 01:30 Beijing (ambiguous, fold=1)",
        m1.utc.strftime("%H:%M"), "17:30")

    m = resolve(dt.datetime(1900, 6, 1, 12, 0), beijing)
    lmt_flag = any(f.startswith("tzdb-lmt-era") for f in m.flags)
    add("1900-06-01 12:00 Beijing (tzdb LMT era +08:05:43)",
        m.utc.strftime("%H:%M:%S") + (" +flag" if lmt_flag else " -flag"), "03:54:17 +flag")

    m = resolve(dt.datetime(1850, 3, 10, 12, 0), beijing, tz="LMT")
    add("1850-03-10 12:00 Beijing LMT (lon 116.4074 -> +07:45:38)",
        m.utc.strftime("%H:%M:%S"), "04:14:22")

    m = resolve(dt.datetime(2000, 1, 1, 12, 0), Place(lat=0, lon=0, tz="UTC+0"))
    ok = abs(m.jd_ut - 2451545.0) < 1.2 / 86400 and 62.0 < m.delta_t_sec < 65.5
    rows.append(("2000-01-01 12:00 UTC -> JD/deltaT sanity",
                 f"jd_ut={m.jd_ut:.8f} dT={m.delta_t_sec:.2f}s",
                 "jd~2451545.0 dT~63.8s", ok))

    m = resolve(dt.datetime(1500, 2, 20, 12, 0), Place(lat=51.5, lon=0.0, tz="LMT"),
                calendar="julian")
    exp_jd = swe.julday(1500, 2, 20, 12.0, swe.JUL_CAL)
    rows.append(("1500-02-20 12:00 julian calendar, LMT lon 0",
                 f"jd_ut={m.jd_ut:.6f}", f"jd_ut={exp_jd:.6f}",
                 abs(m.jd_ut - exp_jd) < 1e-9))
    return rows


def chart_layer_cases() -> list[tuple[str, str, bool]]:
    """M1: snapshot equality + parse round-trip per golden fixture."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(config.REPO_ROOT / "tests" / "golden"))
    from fixtures import ALL, build  # type: ignore
    from ..render import parse, render_chart

    snap_dir = config.REPO_ROOT / "tests" / "golden" / "snapshots"
    rows: list[tuple[str, str, bool]] = []
    for fx in ALL:
        try:
            m, c, hour, stars = build(fx)
            text = render_chart(c, fx.name, hour, stars)
            snap = snap_dir / f"{fx.slug}.txt"
            snap_ok = snap.exists() and snap.read_text(encoding="utf-8") == text
            doc = parse(text)
            rt_ok = (len(doc["sections"]["POINTS"]) ==
                     len([k for k in c.settings.points if k in c.points])
                     and doc["warnings"] == list(c.flags))
            ok = snap_ok and rt_ok
            rows.append((fx.slug, f"snapshot={'=' if snap_ok else 'DIFF'} "
                                  f"roundtrip={'ok' if rt_ok else 'FAIL'}", ok))
        except Exception as exc:  # a fixture must never crash
            rows.append((fx.slug, f"EXCEPTION {type(exc).__name__}: {exc}", False))
    return rows


def dignity_table_checks() -> list[tuple[str, bool]]:
    from ..core.dignities import BOUNDS_EGYPTIAN, DECANS_CHALDEAN, DOMICILE
    from collections import Counter
    checks: list[tuple[str, bool]] = []
    ok = all(b[-1][0] == 30 and
             sorted(p for _, p in b) == sorted(["MERCURY", "VENUS", "MARS",
                                                "JUPITER", "SATURN"])
             for b in BOUNDS_EGYPTIAN)
    checks.append(("egyptian bounds: 12 signs x sum 30 x five planets once", ok))
    flat = [DECANS_CHALDEAN[i][j] for i in range(12) for j in range(3)]
    checks.append(("decans: chaldean period-7, Aries I = Mars",
                   flat[0] == "MARS" and all(a == b for a, b in zip(flat, flat[7:]))))
    cnt = Counter(DOMICILE)
    checks.append(("domiciles: luminaries 1 sign, planets 2 signs",
                   cnt["SUN"] == 1 and cnt["MOON"] == 1 and
                   all(cnt[p] == 2 for p in ("MERCURY", "VENUS", "MARS",
                                             "JUPITER", "SATURN"))))
    return checks


def build_report(path: str | None = None) -> bool:
    eph = Ephemeris()
    jds = _jd_grid()
    pos = compare_positions(eph, jds)
    hou = compare_houses(eph, jds)
    ts = timespace_cases()
    m1 = chart_layer_cases()
    dig = dignity_table_checks()

    pos_ok = all(w["lon"] <= TOL_LON and w["lat"] <= TOL_LAT and w["speed"] <= TOL_SPEED
                 for w in pos.values())
    hou_ok = all(v <= TOL_CUSP for v in hou.values())
    ts_ok = all(r[3] for r in ts)
    m1_ok = all(r[2] for r in m1)
    dig_ok = all(r[1] for r in dig)
    all_ok = pos_ok and hou_ok and ts_ok and m1_ok and dig_ok

    lines: list[str] = []
    a = lines.append
    a("# AstroText verification report")
    a("")
    a(f"- engine: astrotext {__version__} | Swiss Ephemeris {eph.se_version} "
      f"(pyswisseph, built from source) | swetest {swetest_ref.version()}")
    a(f"- ephemeris files: {eph.info()['ephe_files']}")
    a(f"- sample grid: {len(jds)} instants in 1800..2399 (seed {SEED}), "
      f"{len(LOCATIONS)} locations x {len(HOUSE_SYSTEMS)} house systems")
    a(f"- tolerances: lon/lat/speed/cusp <= {TOL_LON} deg ({TOL_LON*3600:.5f} arcsec)")
    a("")
    a(f"## RESULT: {'PASS' if all_ok else 'FAIL'}")
    a("")
    a("## L0 positions vs swetest (max |delta| over grid, degrees)")
    a("")
    a("| point | dlon | dlat | dspeed | ok |")
    a("|---|---|---|---|---|")
    for key in [k for k in SE_POINTS if k in pos]:
        w = pos[key]
        ok = w["lon"] <= TOL_LON and w["lat"] <= TOL_LAT and w["speed"] <= TOL_SPEED
        a(f"| {key} | {w['lon']:.2e} | {w['lat']:.2e} | {w['speed']:.2e} | {'Y' if ok else 'FAIL'} |")
    a("")
    a("## Houses & angles vs swetest (max |delta|, degrees)")
    a("")
    a("| item | max delta | ok |")
    a("|---|---|---|")
    for k, v in hou.items():
        a(f"| {k} | {v:.2e} | {'Y' if v <= TOL_CUSP else 'FAIL'} |")
    a("")
    a("## Time & timezone acceptance cases")
    a("")
    a("| case | got | expected | ok |")
    a("|---|---|---|---|")
    for desc, got, exp, ok in ts:
        a(f"| {desc} | {got} | {exp} | {'Y' if ok else 'FAIL'} |")
    a("")
    a("## M1 chart layer: golden fixtures (snapshot + round-trip)")
    a("")
    a("| fixture | status | ok |")
    a("|---|---|---|")
    for slug, status, ok in m1:
        a(f"| {slug} | {status} | {'Y' if ok else 'FAIL'} |")
    a("")
    a("## Classical table structure")
    a("")
    a("| check | ok |")
    a("|---|---|")
    for desc, ok in dig:
        a(f"| {desc} | {'Y' if ok else 'FAIL'} |")
    a("")

    out = path or str(config.REPO_ROOT / "verification_report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwritten: {out}")
    return all_ok


def main() -> int:
    return 0 if build_report() else 1


if __name__ == "__main__":
    sys.exit(main())
