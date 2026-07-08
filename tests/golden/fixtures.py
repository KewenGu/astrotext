"""Golden fixture cases.

Two groups:
  REAL      well-known public birth data (Astro-Databank AA-rated, from
            memory — re-verify against astro.com during user acceptance;
            their role here is REGRESSION anchoring, which only needs the
            inputs to be fixed and documented).
  SYNTHETIC constructed to pin every edge path: polar fallback, equator,
            southern hemisphere, midnight, DST edges, LMT, julian calendar,
            unknown time.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from astrotext.core.settings import HELLENISTIC, MODERN, Settings
from astrotext.timespace import GREGORIAN, JULIAN, Place


@dataclass(frozen=True)
class Fixture:
    slug: str
    name: str
    local: dt.datetime
    place: Place
    calendar: str = GREGORIAN
    tz: str | None = None          # override place.tz
    fold: int = 0
    settings: Settings = MODERN
    note: str = ""


REAL = [
    Fixture("einstein", "Albert Einstein", dt.datetime(1879, 3, 14, 11, 30),
            Place(48.4011, 9.9876, "Ulm, Germany", "LMT"),
            note="AA; pre-zone-time Germany -> LMT"),
    Fixture("jobs", "Steve Jobs", dt.datetime(1955, 2, 24, 19, 15),
            Place(37.7749, -122.4194, "San Francisco CA", "America/Los_Angeles"),
            note="AA"),
    Fixture("monroe", "Marilyn Monroe", dt.datetime(1926, 6, 1, 9, 30),
            Place(34.0522, -118.2437, "Los Angeles CA", "America/Los_Angeles"),
            note="AA"),
    Fixture("obama", "Barack Obama", dt.datetime(1961, 8, 4, 19, 24),
            Place(21.3069, -157.8583, "Honolulu HI", "Pacific/Honolulu"),
            note="AA"),
    Fixture("freud", "Sigmund Freud", dt.datetime(1856, 5, 6, 18, 30),
            Place(49.6417, 18.3506, "Freiberg (Pribor), Moravia", "LMT"),
            note="AA; LMT era"),
    Fixture("curie", "Marie Curie", dt.datetime(1867, 11, 7, 12, 0),
            Place(52.2297, 21.0122, "Warsaw, Poland", "LMT"),
            note="birth time unverified -> treated as noon example"),
    Fixture("hepburn", "Audrey Hepburn", dt.datetime(1929, 5, 4, 3, 0),
            Place(50.8503, 4.3517, "Brussels, Belgium", "Europe/Brussels"),
            note="AA"),
    Fixture("bruce-lee", "Bruce Lee", dt.datetime(1940, 11, 27, 7, 12),
            Place(37.7749, -122.4194, "San Francisco CA", "America/Los_Angeles"),
            note="AA; also a hellenistic-settings case", ),
]

SYNTHETIC = [
    Fixture("beijing-dst", "Beijing DST-era summer birth",
            dt.datetime(1988, 6, 15, 14, 30),
            Place(39.9042, 116.4074, "Beijing", "Asia/Shanghai"),
            note="China DST +09:00; near-new-moon; OOB Moon (1988 standstill)"),
    Fixture("beijing-dst-ambiguous", "Beijing DST fall-back hour",
            dt.datetime(1986, 9, 14, 1, 30),
            Place(39.9042, 116.4074, "Beijing", "Asia/Shanghai"), fold=1,
            note="ambiguous local time, second occurrence"),
    Fixture("polar", "Longyearbyen polar fallback",
            dt.datetime(1990, 12, 21, 12, 0),
            Place(78.2232, 15.6267, "Longyearbyen, Svalbard", "Europe/Oslo"),
            note="Placidus impossible -> Porphyry flagged; polar night"),
    Fixture("equator", "Quito equator birth",
            dt.datetime(1975, 3, 21, 6, 0),
            Place(-0.1807, -78.4678, "Quito, Ecuador", "America/Guayaquil"),
            note="equator + equinox sunrise"),
    Fixture("sydney", "Sydney southern hemisphere",
            dt.datetime(2000, 1, 1, 0, 1),
            Place(-33.8688, 151.2093, "Sydney, Australia", "Australia/Sydney"),
            note="southern hemisphere + DST + midnight"),
    Fixture("midnight", "Exact midnight London",
            dt.datetime(1970, 1, 1, 0, 0),
            Place(51.5074, -0.1278, "London, UK", "Europe/London"),
            note="epoch midnight; UK on BST(+1) all of 1970 (no DST change)"),
    Fixture("lmt-1850", "Pre-zone China LMT",
            dt.datetime(1850, 3, 10, 12, 0),
            Place(39.9042, 116.4074, "Beijing", None), tz="LMT",
            note="explicit LMT from longitude"),
    Fixture("julian-cal", "Julian calendar birth (Russia 1900)",
            dt.datetime(1900, 6, 1, 6, 0),
            Place(59.9311, 30.3609, "St Petersburg", None), tz="LMT",
            calendar=JULIAN,
            note="Russia kept the Julian calendar until 1918; "
                 "Julian 1900-06-01 = Gregorian 1900-06-14"),
    Fixture("unknown-time", "Unknown birth time (noon chart)",
            dt.datetime(1985, 10, 10, 12, 0),
            Place(31.2304, 121.4737, "Shanghai", "Asia/Shanghai"),
            settings=MODERN.with_(unknown_time=True),
            note="houses/angles/lots suppressed"),
    Fixture("hellenistic", "Hellenistic profile (whole sign, seven)",
            dt.datetime(1988, 6, 15, 14, 30),
            Place(39.9042, 116.4074, "Beijing", "Asia/Shanghai"),
            settings=HELLENISTIC,
            note="same instant as beijing-dst under classical settings"),
    Fixture("high-lat-ok", "Reykjavik below polar circle",
            dt.datetime(1995, 6, 21, 3, 0),
            Place(64.1466, -21.9426, "Reykjavik, Iceland", "Atlantic/Reykjavik"),
            note="64N: Placidus legal but extreme cusps; midsummer"),
    Fixture("retro-heavy", "Retrograde-heavy moment",
            dt.datetime(2022, 9, 18, 21, 0),
            Place(40.7128, -74.0060, "New York NY", "America/New_York"),
            note="Mercury+Jupiter+Saturn+Neptune+Pluto all Rx"),
]

ALL: list[Fixture] = REAL + SYNTHETIC


def build(fx: Fixture):
    """fixture -> (Moment, Chart, hour, star hits) with deterministic parts."""
    from astrotext.core import compute_chart
    from astrotext.core.hours import planetary_hour
    from astrotext.core.stars import star_hits
    from astrotext.timespace import resolve

    m = resolve(fx.local, fx.place, tz=fx.tz, calendar=fx.calendar, fold=fx.fold)
    c = compute_chart(m, fx.settings)
    hour = planetary_hour(m) if not fx.settings.unknown_time else None
    targets = {k: c.points[k].lon for k in c.points}
    if c.angles:
        targets |= {a: c.angles[a] for a in ("ASC", "MC")}
    stars = star_hits(m.jd_ut, targets, fx.settings.fixed_star_orb)
    return m, c, hour, stars


# ---- M2: timed reports (transits/progressions/solar arc) -------------------

import datetime as _dt

#: frozen "now" for timed snapshots — deterministic across runs
TIMED_NOW_UTC = _dt.datetime(2026, 7, 8, 12, 0, tzinfo=_dt.timezone.utc)
TIMED_PLACE = Place(40.7128, -74.0060, "New York NY", "America/New_York")
TIMED_SLUGS = ("beijing-dst", "einstein")


def build_timed(fx):
    """fixture -> {report_name: rendered_text} at the frozen now-moment."""
    from astrotext.render.timed import (
        render_progressed, render_solar_arc, render_transits,
    )
    from astrotext.techniques import (
        compute_progressed, compute_solar_arc, compute_transits,
    )
    from astrotext.timespace import from_utc

    _, natal, _, _ = build(fx)
    now = from_utc(TIMED_NOW_UTC, TIMED_PLACE)
    from astrotext.render.timed import (
        render_firdaria, render_profections, render_return,
    )
    from astrotext.techniques.firdaria import firdaria
    from astrotext.techniques.profections import profections
    from astrotext.techniques.returns import compute_return

    out = {
        "transits": render_transits(compute_transits(natal, now), fx.name),
        "secondary": render_progressed(
            compute_progressed(natal, now, "secondary"), fx.name),
        "tertiary": render_progressed(
            compute_progressed(natal, now, "tertiary"), fx.name),
        "solar-arc": render_solar_arc(compute_solar_arc(natal, now), fx.name),
        "solar-return": render_return(
            compute_return(natal, now, "SUN"), fx.name),
        "lunar-return": render_return(
            compute_return(natal, now, "MOON"), fx.name),
        "firdaria": render_firdaria(firdaria(natal), natal, fx.name),
        "profections": render_profections(profections(natal, now), fx.name),
    }
    from astrotext.render.vedic import (
        render_vargas, render_vedic_rashi, render_vimshottari,
    )
    from astrotext.techniques.vedic import (
        compute_vedic_chart, varga_table, vimshottari,
    )
    m2 = build(fx)[0]
    vc = compute_vedic_chart(m2)
    vlons = {k: vc.grahas[k].lon for k in vc.grahas}
    if vc.lagna is not None:
        vlons["LAGNA"] = vc.lagna
    out["vedic-rashi"] = render_vedic_rashi(vc, fx.name)
    out["vedic-vargas"] = render_vargas(vc, varga_table(vlons, vc.settings.vargas), fx.name)
    out["vedic-vimshottari"] = render_vimshottari(
        vimshottari(vc.grahas["MOON"].lon, m2.jd_ut), vc, now.jd_ut, fx.name)
    return out
