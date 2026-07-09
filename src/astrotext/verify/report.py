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

try:
    import swisseph as swe
except ImportError:          # de440-only environment: the swiss
    swe = None               # reference harness needs `make vendor`

from .. import __version__, config
from ..core.angles import angdiff
from ..ephem import SE_POINTS, Ephemeris
from ..timespace import NonexistentLocalTime, Place, resolve
from . import swetest_ref

# ---- acceptance gates, degrees ---------------------------------------------
# The report compares the *default* backend against swetest.  The gate depends
# on which backend is active:
#
#   swiss  — our wrapper must reproduce swetest bit-for-bit (swetest prints 7
#            decimals => 5e-8 deg quantization floor).  Uniform tight gate.
#   de440  — the clean-room kernel differs from Swiss Ephemeris by *real,
#            attributed* amounts, measured module-by-module in
#            tools/verify_kernel.py and documented in docs/KERNEL.md: the
#            DE431(SE data)->DE440 lunar term, newer JPL Lilith/Chiron orbit
#            solutions, SE's long-term sidereal-time splice (houses/angles at
#            span edges + high latitude), and SE's own *reported* speeds
#            (less accurate than the true derivative the kernel emits).  The
#            gates below are those measured bounds with headroom for the
#            UT/CLI path; any exceedance is a regression, not a model gap.
_AS = 1.0 / 3600.0        # one arcsecond, in degrees
TOL_SWISS = 2e-7          # 0.00072 arcsec — bit-parity floor

#: de440 vs swetest, max |Δ| over the 1800-2399 grid: (lon, lat, lon_speed) deg
_DE440_POS = {
    # planet speed gate 2e-5 °/day (0.072"/day): SE's *reported* speed
    # polynomial imprecision (K2), not our derivative — e.g. Venus rides
    # ~1.4e-5 at grid edges.
    "SUN":     (0.05 * _AS, 0.10 * _AS, 2.0e-5),
    "MERCURY": (0.05 * _AS, 0.10 * _AS, 2.0e-5),
    "VENUS":   (0.05 * _AS, 0.10 * _AS, 2.0e-5),
    "MARS":    (0.05 * _AS, 0.10 * _AS, 2.0e-5),
    "JUPITER": (0.05 * _AS, 0.10 * _AS, 2.0e-5),
    "SATURN":  (0.05 * _AS, 0.10 * _AS, 2.0e-5),
    "URANUS":  (0.05 * _AS, 0.10 * _AS, 2.0e-5),
    "NEPTUNE": (0.05 * _AS, 0.10 * _AS, 2.0e-5),
    "PLUTO":   (0.05 * _AS, 0.10 * _AS, 2.0e-5),
    "MOON":    (0.05 * _AS, 0.05 * _AS, 1.2e-4),
    "TRUE_NODE":   (0.10 * _AS, 1e-6, 1.0e-4),
    "MEAN_NODE":   (0.80 * _AS, 1e-6, 1.0e-5),
    "MEAN_APOGEE": (2.00 * _AS, 0.30 * _AS, 1.0e-5),
    "CHIRON":      (5.00 * _AS, 1.00 * _AS, 1.2e-5),
}
#: de440 vs swetest end-to-end (time->ARMC->houses); SE sidereal-time splice
#: dominates at span edges / high latitude (K4).
_DE440_HOUSE = {"cusp": 25 * _AS, "ASC": 25 * _AS, "MC": 15 * _AS,
                "ARMC": 12 * _AS, "VERTEX": 20 * _AS}
_DE440_SID = 0.02 * _AS   # sidereal longitude vs swetest -sid1 (K5)


def _pos_ok(backend: str, key: str, w: dict[str, float]) -> bool:
    if backend == "swiss":
        return (w["lon"] <= TOL_SWISS and w["lat"] <= TOL_SWISS
                and w["speed"] <= TOL_SWISS)
    gl, gb, gs = _DE440_POS[key]
    return w["lon"] <= gl and w["lat"] <= gb and w["speed"] <= gs


def _house_ok(backend: str, k: str, v: float) -> bool:
    return v <= (TOL_SWISS if backend == "swiss" else _DE440_HOUSE[k])


def _sid_gate(backend: str) -> float:
    return TOL_SWISS if backend == "swiss" else _DE440_SID

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


def timed_layer_cases() -> list[tuple[str, str, bool]]:
    """M2: transit/progression/solar-arc snapshot + invariants."""
    import sys
    sys.path.insert(0, str(config.REPO_ROOT / "tests" / "golden"))
    from fixtures import ALL, TIMED_SLUGS, build, build_timed  # type: ignore
    from ..core.angles import angdiff, norm360
    from ..techniques import compute_progressed, compute_solar_arc
    from ..timespace import from_utc
    from fixtures import TIMED_NOW_UTC, TIMED_PLACE  # type: ignore

    snap_dir = config.REPO_ROOT / "tests" / "golden" / "snapshots"
    rows: list[tuple[str, str, bool]] = []
    now = from_utc(TIMED_NOW_UTC, TIMED_PLACE)
    for fx in [f for f in ALL if f.slug in TIMED_SLUGS]:
        try:
            texts = build_timed(fx)
            snaps_ok = all(
                (snap_dir / f"{fx.slug}--{n}.txt").exists() and
                (snap_dir / f"{fx.slug}--{n}.txt").read_text(encoding="utf-8") == t
                for n, t in texts.items())
            _, natal, _, _ = build(fx)
            sec = compute_progressed(natal, now, "secondary")
            sa = compute_solar_arc(natal, now)
            sun_disp = norm360(sec.chart.points["SUN"].lon - natal.points["SUN"].lon)
            inv_ok = abs(angdiff(sa.arc, sun_disp)) < 1e-9
            age0 = compute_progressed(natal, natal.moment, "secondary")
            inv_ok &= all(abs(angdiff(p.lon, natal.points[k].lon)) < 1e-9
                          for k, p in age0.chart.points.items())
            rows.append((fx.slug,
                         f"snapshots={'=' if snaps_ok else 'DIFF'} "
                         f"arc==dSun & age0==natal: {'ok' if inv_ok else 'FAIL'}",
                         snaps_ok and inv_ok))
        except Exception as exc:
            rows.append((fx.slug, f"EXCEPTION {type(exc).__name__}: {exc}", False))
    return rows


def vedic_layer_cases() -> list[tuple[str, str, bool]]:
    """M5: sidereal vs swetest -sid1, plus structural invariants."""
    import random
    import subprocess

    from ..core.angles import angdiff
    from ..ephem.engine import Ephemeris
    from ..techniques.vedic import DASHA_YEARS, varga_sign, vargottama

    rows: list[tuple[str, str, bool]] = []
    eph = Ephemeris()
    eph.configure_sidereal("lahiri")
    rng = random.Random(SEED)
    worst = 0.0
    import swisseph as swe
    jds = [2451545.0] + [rng.uniform(swe.julday(1850, 1, 5, 0),
                                     swe.julday(2200, 12, 25, 0))
                         for _ in range(10)]
    import re
    num = re.compile(r"^(\w[\w ]*?)\s+(-?\d+\.\d+)")
    names = {"Sun": "SUN", "Moon": "MOON", "Mercury": "MERCURY",
             "Venus": "VENUS", "Mars": "MARS", "Jupiter": "JUPITER",
             "Saturn": "SATURN"}
    for jd in jds:
        out = subprocess.run(
            [str(config.swetest_bin()), f"-edir{config.ephe_path()}",
             f"-bj{jd!r}", "-ut", "-p0123456", "-sid1", "-fPlbs", "-head"],
            capture_output=True, text=True, timeout=60).stdout
        for line in out.splitlines():
            m = num.match(line)
            if m and m.group(1).strip() in names:
                ours = eph.state(jd, names[m.group(1).strip()], sidereal=True).lon
                worst = max(worst, abs(angdiff(ours, float(m.group(2)))))
    rows.append(("sidereal positions vs swetest -sid1 (Lahiri)",
                 f"max|delta|={worst:.2e} deg over {len(jds)} instants x 7 grahas",
                 worst <= _sid_gate(eph.backend)))

    ok_v = True
    for _ in range(300):
        lon = rng.uniform(0, 360)
        for d in (1, 2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60):
            s, _p = varga_sign(lon, d)
            ok_v &= 0 <= s <= 11
        ok_v &= vargottama(lon) == (varga_sign(lon, 1)[0] == varga_sign(lon, 9)[0])
    rows.append(("16 vargas: valid signs + vargottama definition",
                 "300 random longitudes x 16 charts", ok_v))
    rows.append(("vimshottari lord years sum", f"{sum(DASHA_YEARS.values())}",
                 sum(DASHA_YEARS.values()) == 120))
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
    m2 = timed_layer_cases()
    m5 = vedic_layer_cases()
    dig = dignity_table_checks()

    backend = eph.backend
    pos_ok = all(_pos_ok(backend, k, w) for k, w in pos.items())
    hou_ok = all(_house_ok(backend, k, v) for k, v in hou.items())
    ts_ok = all(r[3] for r in ts)
    m1_ok = all(r[2] for r in m1)
    m2_ok = all(r[2] for r in m2)
    m5_ok = all(r[2] for r in m5)
    dig_ok = all(r[1] for r in dig)
    all_ok = pos_ok and hou_ok and ts_ok and m1_ok and m2_ok and m5_ok and dig_ok

    lines: list[str] = []
    a = lines.append
    a("# AstroText verification report")
    a("")
    a(f"- engine: astrotext {__version__} | backend: {backend} "
      f"({eph.se_version}) | reference: swetest {swetest_ref.version()}")
    a(f"- ephemeris files: {eph.info()['ephe_files']}")
    a(f"- sample grid: {len(jds)} instants in 1800..2399 (seed {SEED}), "
      f"{len(LOCATIONS)} locations x {len(HOUSE_SYSTEMS)} house systems")
    if backend == "swiss":
        a(f"- gate: swiss backend must match swetest bit-for-bit "
          f"(<= {TOL_SWISS} deg = {TOL_SWISS*3600:.5f} arcsec)")
    else:
        a("- gate: de440 backend vs swetest uses the measured, attributed "
          "per-point bounds from tools/verify_kernel.py / docs/KERNEL.md "
          "(DE431->DE440 lunar term; newer Lilith/Chiron solutions; SE's "
          "sidereal-time splice for houses at span edges + high latitude; "
          "SE's imprecise reported speeds). Deltas within gate = physically "
          "identical, not a wrapper error.")
    a("")
    a(f"## RESULT: {'PASS' if all_ok else 'FAIL'}")
    a("")
    a("## L0 positions vs swetest (max |delta| over grid, degrees)")
    a("")
    a("| point | dlon | dlat | dspeed | ok |")
    a("|---|---|---|---|---|")
    for key in [k for k in SE_POINTS if k in pos]:
        w = pos[key]
        ok = _pos_ok(backend, key, w)
        a(f"| {key} | {w['lon']:.2e} | {w['lat']:.2e} | {w['speed']:.2e} | {'Y' if ok else 'FAIL'} |")
    a("")
    a("## Houses & angles vs swetest (max |delta|, degrees)")
    a("")
    a("| item | max delta | ok |")
    a("|---|---|---|")
    for k, v in hou.items():
        a(f"| {k} | {v:.2e} | {'Y' if _house_ok(backend, k, v) else 'FAIL'} |")
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
    a("## M2 timed layer: transits / progressions / solar arc")
    a("")
    a("| fixture | status | ok |")
    a("|---|---|---|")
    for slug, status, ok in m2:
        a(f"| {slug} | {status} | {'Y' if ok else 'FAIL'} |")
    a("")
    a("## M5 vedic layer")
    a("")
    a("| check | detail | ok |")
    a("|---|---|---|")
    for name, detail, ok in m5:
        a(f"| {name} | {detail} | {'Y' if ok else 'FAIL'} |")
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
