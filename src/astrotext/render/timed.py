"""Renderers for time-based reports: transits, progressions, solar arc.

Same line grammar as text.py (docs/FORMAT.md).  Moving-side keys are
prefixed t. / p. / d. (transiting / progressed / directed), natal side n.
"""
from __future__ import annotations

import swisseph as swe

from ..techniques.progressions import ProgressedReport, SolarArcReport
from ..techniques.transits import TransitReport
from .text import FORMAT_VERSION, dms

__all__ = ["render_transits", "render_progressed", "render_solar_arc", "jd_to_iso"]


def jd_to_iso(jd_ut: float, seconds: bool = False) -> str:
    y, mo, d, h = swe.revjul(jd_ut, swe.GREG_CAL)
    hh = int(h)
    mi_f = (h - hh) * 60
    mi = int(mi_f)
    ss = (mi_f - mi) * 60
    if seconds:
        s = int(round(ss))
        if s == 60:
            s = 0
            mi += 1
            if mi == 60:
                mi = 0
                hh += 1  # good enough for display; jd carries the truth
        return f"{y:04d}-{mo:02d}-{d:02d} {hh:02d}:{mi:02d}:{s:02d}Z"
    if round(ss) >= 30:
        mi += 1
        if mi == 60:
            mi = 0
            hh += 1
    if hh == 24:
        hh = 0  # display-only wrap; date very slightly off at midnight edge
    return f"{y:04d}-{mo:02d}-{d:02d} {hh:02d}:{mi:02d}Z"


def _natal_ref(natal) -> list[str]:
    m = natal.moment
    return [
        f"natal-ref={m.local.isoformat(sep=' ')} @ {m.place.label()} "
        f"tz={m.tz_used} jd-ut={m.jd_ut:.8f}",
    ]


def render_transits(rep: TransitReport, subject: str | None = None) -> str:
    L: list[str] = [f"== ASTROTEXT TRANSITS {FORMAT_VERSION} =="]
    if subject:
        L.append(f"subject={subject}")
    m = rep.sky.moment
    L.append(f"moment-utc={m.utc.strftime('%Y-%m-%d %H:%M:%S')} jd-ut={m.jd_ut:.8f}")
    L.append(f"location={m.place.label()} (transit houses relocated here; "
             f"natal-wheel houses use natal cusps)")
    L += _natal_ref(rep.natal)
    L.append(f"orb={rep.orb:g} aspects=majors "
             f"exact-search-window=+-{rep.window_days:g}d")
    for fl in rep.sky.flags:
        L.append(f"warning={fl}")

    L.append("")
    L.append("-- TRANSIT POINTS --")
    L.append("# point | position | natal-house | sky-house | lon | speed | tags")
    for k, nh in rep.natal_wheel_houses.items():
        p = rep.sky.points[k]
        tags = ",".join(t for t in ("R" if p.retrograde else "",
                                    "OOB" if p.oob else "") if t) or "-"
        sky_h = f"H{p.house}" if p.house else "-"
        nat_h = f"H{nh}" if nh else "-"
        L.append(f"t.{k} | {dms(p.lon)} | {nat_h} | {sky_h} | {p.lon:.6f} | "
                 f"{p.lon_speed:+.6f} | {tags}")

    L.append("")
    L.append("-- TRANSIT->NATAL ASPECTS --")
    L.append("# transiting | aspect | natal | orb(signed) | phase | exact times in window")
    if rep.hits:
        for h in rep.hits:
            exacts = "; ".join(jd_to_iso(j) for j in h.exact_jds) or "(none in window)"
            L.append(f"t.{h.t_point} | {h.aspect.abbr} {h.aspect.angle:g} | "
                     f"n.{h.n_point} | {h.orb_signed:+.3f} | {h.phase} | {exacts}")
    else:
        L.append("(none)")
    L.append("")
    L.append("== END ==")
    return "\n".join(L) + "\n"


def render_progressed(rep: ProgressedReport, subject: str | None = None) -> str:
    kind = rep.kind.upper()
    L: list[str] = [f"== ASTROTEXT {kind}-PROGRESSED {FORMAT_VERSION} =="]
    if subject:
        L.append(f"subject={subject}")
    L.append(f"target-jd-ut={rep.target_jd_ut:.8f} ({jd_to_iso(rep.target_jd_ut)})")
    L.append(f"progressed-jd-ut={rep.prog_jd_ut:.8f} ({jd_to_iso(rep.prog_jd_ut, seconds=True)})")
    L.append(f"clock={rep.clock} age={rep.age_years:.4f}yr")
    L += _natal_ref(rep.natal)
    for fl in rep.chart.flags:
        L.append(f"warning={fl}")

    L.append("")
    L.append("-- PROGRESSED POINTS --")
    L.append("# point | position | natal-house | lon | speed(prog-day) | tags")
    for k, p in rep.chart.points.items():
        nh = rep.natal_wheel_houses.get(k)
        tags = "R" if p.retrograde else "-"
        L.append(f"p.{k} | {dms(p.lon)} | {'H%d' % nh if nh else '-'} | "
                 f"{p.lon:.6f} | {p.lon_speed:+.6f} | {tags}")

    if rep.angles_sa is not None:
        L.append("")
        L.append(f"-- PROGRESSED ANGLES (method {rep.angles_sa.method}) --")
        L.append(f"p.MC | {dms(rep.angles_sa.mc)} | {rep.angles_sa.mc:.6f}")
        L.append(f"p.ASC | {dms(rep.angles_sa.asc)} | {rep.angles_sa.asc:.6f}")
        L.append(f"p.ARMC | - | {rep.angles_sa.armc:.6f}")
    if rep.chart.angles is not None:
        L.append("")
        L.append("-- PROGRESSED ANGLES (method chart/quotidian) --")
        for a in ("ASC", "MC"):
            L.append(f"p.{a} | {dms(rep.chart.angles[a])} | {rep.chart.angles[a]:.6f}")

    L.append("")
    L.append("-- PROGRESSED->NATAL ASPECTS (majors, orb 1.0) --")
    if rep.hits:
        for h in rep.hits:
            L.append(f"{h.p1} | {h.aspect.abbr} {h.aspect.angle:g} | n.{h.p2} | "
                     f"{h.orb_signed:+.3f} | {h.phase}")
    else:
        L.append("(none)")
    L.append("")
    L.append("== END ==")
    return "\n".join(L) + "\n"


def render_solar_arc(rep: SolarArcReport, subject: str | None = None) -> str:
    L: list[str] = [f"== ASTROTEXT SOLAR-ARC {FORMAT_VERSION} =="]
    if subject:
        L.append(f"subject={subject}")
    L.append(f"target-jd-ut={rep.target_jd_ut:.8f} ({jd_to_iso(rep.target_jd_ut)})")
    L.append(f"arc={rep.arc:.6f} (secondary Sun, year={rep.year})")
    L += _natal_ref(rep.natal)

    L.append("")
    L.append("-- DIRECTED POINTS (natal + arc) --")
    L.append("# point | position | lon")
    for k, lon in rep.directed.items():
        L.append(f"d.{k} | {dms(lon)} | {lon:.6f}")

    L.append("")
    L.append("-- DIRECTED->NATAL ASPECTS (majors, orb 1.0) --")
    if rep.hits:
        for h in rep.hits:
            L.append(f"{h.p1} | {h.aspect.abbr} {h.aspect.angle:g} | n.{h.p2} | "
                     f"{h.orb_signed:+.3f} | -")
    else:
        L.append("(none)")
    L.append("")
    L.append("== END ==")
    return "\n".join(L) + "\n"
