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

    if rep.moon_void is not None:
        v = rep.moon_void
        from ..core.zodiac import SIGNS_ABBR
        L.append("")
        L.append("-- MOON VOID-OF-COURSE (classical: majors to the seven) --")
        L.append(f"void={'yes' if v.is_void else 'no'} | moon-sign={SIGNS_ABBR[v.moon_sign]} | "
                 f"sign-exit={jd_to_iso(v.sign_exit_jd)}")
        if v.last_exact:
            L.append(f"last-exact={v.last_exact[1]} {v.last_exact[0]} @ {jd_to_iso(v.last_exact[2])}")
        if v.next_exact:
            tag = " (after sign change)" if v.next_is_after_sign_change else ""
            L.append(f"next-exact={v.next_exact[1]} {v.next_exact[0]} @ {jd_to_iso(v.next_exact[2])}{tag}")
    L.append("")
    L.append("== END ==")
    return "\n".join(L) + "\n"


def render_return(rep, subject: str | None = None, hour=None, stars=None) -> str:
    """A return chart is a full chart; we prepend the return-specific meta."""
    from .text import render_chart
    extra = (
        f"return-of={rep.body} natal-lon-used={rep.natal_lon_used:.6f} "
        f"precessed={'yes' if rep.precessed else 'no'}",
        f"active-return-jd={rep.active_jd:.8f} ({jd_to_iso(rep.active_jd, seconds=True)}) "
        f"residual={rep.residual_deg * 3600:.4f}arcsec",
        f"next-return-jd={rep.next_jd:.8f} ({jd_to_iso(rep.next_jd, seconds=True)})",
        f"natal-ref-jd={rep.natal.moment.jd_ut:.8f}",
        f"cast-at={rep.location.label()} (current residence by default)",
    )
    return render_chart(rep.chart, subject, hour, stars, extra_meta=extra)


def render_firdaria(periods, natal, subject: str | None = None,
                    nodes: str = "after-mars") -> str:
    L: list[str] = [f"== ASTROTEXT FIRDARIA {FORMAT_VERSION} =="]
    if subject:
        L.append(f"subject={subject}")
    L += _natal_ref(natal)
    L.append(f"sect={'day' if natal.is_day else 'night'} sequence | "
             f"node-placement={nodes}")
    L.append("# level | lord (major/sub) | ages | dates")
    L.append("")
    L.append("-- FIRDARIA TIMELINE --")
    for p in periods:
        d0, d1 = jd_to_iso(p.start_jd)[:10], jd_to_iso(p.end_jd)[:10]
        if p.level == 1:
            L.append(f"MAJOR {p.lord} | {p.start_age:.2f}-{p.end_age:.2f} | {d0} .. {d1}")
        else:
            L.append(f"  sub {p.major_lord}/{p.lord} | {p.start_age:.2f}-{p.end_age:.2f} | {d0} .. {d1}")
    L.append("")
    L.append("== END ==")
    return "\n".join(L) + "\n"


def render_profections(rep, subject: str | None = None) -> str:
    from ..core.zodiac import SIGNS_ABBR
    L: list[str] = [f"== ASTROTEXT PROFECTIONS {FORMAT_VERSION} =="]
    if subject:
        L.append(f"subject={subject}")
    L += _natal_ref(rep.natal)
    L.append("year-boundaries=actual solar returns; months=year/12 equal parts")
    cur = rep.current
    if cur is not None:
        L.append(f"current-year=age {cur.age} | ASC-profects-to {SIGNS_ABBR[cur.asc_sign]} "
                 f"| year-lord={cur.year_lord}")
        L.append(f"current-month=no.{rep.current_month_index + 1} | "
                 f"{SIGNS_ABBR[rep.current_month_sign]} | month-lord={rep.current_month_lord}")
        if rep.profected_mc_sign is not None:
            L.append(f"profected-MC={SIGNS_ABBR[rep.profected_mc_sign]}")
        if rep.profected_fortune_sign is not None:
            L.append(f"profected-FORTUNE={SIGNS_ABBR[rep.profected_fortune_sign]}")
    L.append("")
    L.append("-- PROFECTION YEARS (age | sign | lord | starts) --")
    for y in rep.years:
        mark = " <== current" if cur is not None and y.age == cur.age else ""
        L.append(f"{y.age} | {SIGNS_ABBR[y.asc_sign]} | {y.year_lord} | "
                 f"{jd_to_iso(y.start_jd)[:10]}{mark}")
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
