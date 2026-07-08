"""Plain-text renderer, format v0 — the product surface for AI agents.

Grammar (docs/FORMAT.md is the normative spec):
  line 1            == ASTROTEXT <KIND> v0 ==
  meta lines        key=value            (no '|' in values)
  section header    -- NAME --
  table row         field | field | ...  (first field is the row key)
  comment           # ...                (column legend, ignorable)

Determinism: fixed point order (settings order), fixed float precision
(longitude 6dp, deltas 3dp), no timestamps except the chart's own.  Rendering
the same Chart twice yields byte-identical text (tested).
"""
from __future__ import annotations

from ..core.angles import deg_to_dms
from ..core.chart import Chart
from ..core.dignities import SCORE_WEIGHTS
from ..core.hours import PlanetaryHour
from ..core.stars import StarHit
from ..core.zodiac import SIGNS_ABBR
from ..ephem.points import REGISTRY

__all__ = ["dms", "sf", "render_chart"]

FORMAT_VERSION = "v0"


def sf(x: float, nd: int) -> str:
    """Signed fixed-point with CANONICAL ZERO.

    Cross-compiler float differences flip the sign of +-1ulp values (the
    node-node opposition orb is exactly 180 deg +- 1ulp), and IEEE keeps
    -0.0 through rounding — so Linux rendered '-0.000' where macOS
    rendered '+0.000'. Adding +0.0 after rounding folds -0.0 to +0.0,
    making the text view platform-stable at display precision."""
    return f"{round(x, nd) + 0.0:+.{nd}f}"


def dms(lon: float) -> str:
    """298.7654 -> '28Cap45\\'55\"' — zodiacal degrees-minutes-seconds."""
    sign_no = int(lon // 30) % 12
    _s, d, m, s = deg_to_dms(lon % 30.0, 0)
    if d == 30:  # carry across a sign boundary from rounding
        sign_no, d = (sign_no + 1) % 12, 0
    return f"{d:02d}{SIGNS_ABBR[sign_no]}{m:02d}'{int(s):02d}\""


def _meta(chart: Chart, subject: str | None,
          extra_meta: tuple[str, ...] = ()) -> list[str]:
    m = chart.moment
    L: list[str] = []
    L.append(f"== ASTROTEXT {chart.kind.upper()} {FORMAT_VERSION} ==")
    if subject:
        L.append(f"subject={subject}")
    L.extend(extra_meta)
    L.append(f"local={m.local.isoformat(sep=' ')} calendar={m.calendar}")
    L.append(f"place={m.place.label()} tz={m.tz_used}")
    off = m.utc_offset.total_seconds()
    sign = "+" if off >= 0 else "-"
    off = abs(off)
    L.append(f"utc={m.utc.strftime('%Y-%m-%d %H:%M:%S')} "
             f"offset={sign}{int(off//3600):02d}:{int(off%3600//60):02d}:{int(off%60):02d}")
    L.append(f"jd-ut={m.jd_ut:.8f} delta-t={m.delta_t_sec:+.2f}s")
    for line in chart.settings.describe():
        L.append(f"set:{line}")
    if chart.house_system_used:
        L.append(f"houses-used={chart.house_system_used}")
    if chart.is_day is not None:
        alt = f" sun-altitude={chart.sun_altitude:+.2f}" if chart.sun_altitude is not None else ""
        L.append(f"sect={'day' if chart.is_day else 'night'}{alt}")
    L.append(f"obliquity={chart.obliquity:.6f}")
    if chart.flags:
        for fl in chart.flags:
            L.append(f"warning={fl}")
    else:
        L.append("warning=(none)")
    return L


def render_chart(chart: Chart, subject: str | None = None,
                 hour: PlanetaryHour | None = None,
                 stars: list[StarHit] | None = None,
                 extra_meta: tuple[str, ...] = ()) -> str:
    L = _meta(chart, subject, extra_meta)
    p = chart.points

    # ---- points -------------------------------------------------------------
    L.append("")
    L.append("-- POINTS --")
    L.append("# point | position | house | lon | lat | speed | decl | tags")
    for k in chart.settings.points:
        if k not in p:
            continue
        pt = p[k]
        tags = ",".join(t for t in (
            "R" if pt.retrograde else "", "OOB" if pt.oob else "")) or "-"
        tags = tags.strip(",") or "-"
        house = f"H{pt.house}" if pt.house else "-"
        L.append(
            f"{k} | {dms(pt.lon)} | {house} | {pt.lon:.6f} | {sf(pt.lat, 6)} | "
            f"{sf(pt.lon_speed, 6)} | {sf(pt.dec, 4)} | {tags}"
        )

    # ---- angles & houses ------------------------------------------------------
    if chart.angles is not None:
        L.append("")
        L.append("-- ANGLES --")
        for a in ("ASC", "MC", "DSC", "IC", "VERTEX", "ARMC"):
            L.append(f"{a} | {dms(chart.angles[a])} | {chart.angles[a]:.6f}")
    if chart.cusps is not None:
        L.append("")
        L.append(f"-- HOUSES ({chart.house_system_used}) --")
        for i, c in enumerate(chart.cusps, 1):
            L.append(f"H{i} | {dms(c)} | {c:.6f}")

    # ---- aspects ---------------------------------------------------------------
    L.append("")
    L.append("-- ASPECTS --")
    L.append("# p1 | aspect | p2 | orb(deg,signed=sep-exact) | A=applying S=separating E=exact")
    if chart.aspects:
        for h in chart.aspects:
            L.append(f"{h.p1} | {h.aspect.abbr} {h.aspect.angle:g} | {h.p2} | "
                     f"{sf(h.orb_signed, 3)} | {h.phase}")
    else:
        L.append("(none)")

    # ---- dignities ----------------------------------------------------------------
    if chart.dignities:
        L.append("")
        day = chart.is_day if chart.is_day is not None else True
        L.append(f"-- DIGNITIES (classical seven, {'day' if day else 'night'} chart) --")
        L.append("# planet | essential | score | rulers-of-its-position: sign/exalt/trip(day,night,part)/bound/decan")
        for k in [k for k in chart.settings.points if k in chart.dignities]:
            d = chart.dignities[k]
            ess = ",".join(d.dignities) if d.dignities else "peregrine"
            if d.peregrine and d.dignities:
                ess += ",peregrine"
            trip = ",".join(d.triplicity_rulers)
            L.append(
                f"{k} | {ess} | {d.score:+d} | {d.sign_ruler}/"
                f"{d.exalted_here or '-'}/({trip})/{d.bound_ruler}/{d.decan_ruler}"
            )
        L.append(f"# score weights: " + " ".join(
            f"{k}{v:+d}" for k, v in SCORE_WEIGHTS.items()))

    # ---- receptions & dispositors ---------------------------------------------------
    L.append("")
    L.append("-- RECEPTIONS (mutual) --")
    if chart.receptions:
        for a, b, kind in chart.receptions:
            L.append(f"{a} <-> {b} | {kind}")
    else:
        L.append("(none)")
    if chart.dispositors:
        L.append("")
        L.append("-- DISPOSITORS (domicile chains) --")
        for k, chain in chart.dispositors.items():
            if len(chain) >= 2 and chain[-1] == chain[-2]:
                pretty = " > ".join(chain[:-1]) + " (final)"
            else:
                pretty = " > ".join(chain) + " (loop)"
            L.append(f"{k} | {pretty}")

    # ---- lots, moon -------------------------------------------------------------------
    if chart.lots:
        L.append("")
        L.append("-- LOTS --")
        for k in ("FORTUNE", "SPIRIT"):
            if k in chart.lots:
                lon = chart.lots[k]
                house = ""
                if chart.cusps:
                    from ..core.chart import _house_of
                    house = f" | H{_house_of(lon, chart.cusps)}"
                L.append(f"{k} | {dms(lon)} | {lon:.6f}{house}")
    L.append("")
    L.append("-- MOON --")
    mi = chart.moon
    L.append(f"phase={mi.phase} | waxing={'yes' if mi.waxing else 'no'} | "
             f"elongation={mi.elongation:.3f} | illumination={mi.illumination:.3f}")

    # ---- antiscia -----------------------------------------------------------------------
    L.append("")
    L.append(f"-- ANTISCIA (orb {chart.settings.antiscia_orb:g}) --")
    if chart.antiscia:
        for p1, kind, p2, delta in chart.antiscia:
            L.append(f"{p1} | {kind} | {p2} | {sf(delta, 3)}")
    else:
        L.append("(none)")

    # ---- stars ---------------------------------------------------------------------------
    if stars is not None:
        L.append("")
        L.append(f"-- FIXED STARS (conjunctions, orb {chart.settings.fixed_star_orb:g}) --")
        if stars:
            for h in stars:
                L.append(f"{h.star} | {dms(h.star_lon)} | conj {h.target} | {sf(h.delta, 3)}")
        else:
            L.append("(none)")

    # ---- planetary hour -------------------------------------------------------------------
    if hour is not None:
        L.append("")
        L.append("-- PLANETARY HOUR --")
        if hour.polar:
            L.append("polar-regime: sun does not rise/set here on this date; hours undefined")
        else:
            L.append(f"day={hour.day_ruler}({hour.weekday}) | "
                     f"hour={hour.hour_ruler} (no.{hour.hour_no}, "
                     f"{'day' if hour.is_day_hour else 'night'})")

    L.append("")
    L.append("== END ==")
    return "\n".join(L) + "\n"
