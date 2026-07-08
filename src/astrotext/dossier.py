"""Dossier generator (M4): one call -> a person's complete plain-text
astrological database.

Layout (numbers give agents a stable reading order):

    <slug>/
      index.txt                how to read this dossier (for AI agents)
      00_meta.txt              input echo, resolved time/place, settings,
                               engine versions, warnings, EN->ZH glossary
      10_natal.txt             modern natal (Placidus, full classical pack)
      11_natal_hellenistic.txt whole-sign, classical seven view
      20_transits.txt          sky-now vs natal + exact timestamps + Moon VOC
      21_secondary.txt  22_tertiary.txt  23_solar_arc.txt
      30_solar_return.txt      31_lunar_return.txt
      40_firdaria.txt          41_profections.txt

Determinism: same inputs (including the target moment) -> byte-identical
dossier.  The target moment is an explicit argument, never wall-clock.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .core import HELLENISTIC, MODERN, Settings, compute_chart
from .core.chart import Chart, default_ephemeris
from .core.hours import planetary_hour
from .core.stars import star_hits
from .render import render_chart, render_glossary
from .render.timed import (
    jd_to_iso, render_firdaria, render_profections, render_progressed,
    render_return, render_solar_arc, render_transits,
)
from .techniques import (
    compute_progressed, compute_solar_arc, compute_transits,
)
from .techniques.firdaria import firdaria
from .techniques.profections import profections
from .techniques.returns import compute_return
from .timespace import Moment, Place, from_utc, resolve

__all__ = ["Subject", "generate_dossier"]


@dataclass(frozen=True)
class Subject:
    name: str
    local: dt.datetime              # naive birth clock time
    place: Place
    tz: str | None = None           # override place.tz
    calendar: str = "gregorian"
    fold: int = 0
    unknown_time: bool = False


def _natal(subject: Subject, settings: Settings) -> tuple[Moment, Chart]:
    if subject.unknown_time:
        settings = settings.with_(unknown_time=True)
    m = resolve(subject.local, subject.place, tz=subject.tz,
                calendar=subject.calendar, fold=subject.fold)
    return m, compute_chart(m, settings)


def generate_dossier(
    subject: Subject,
    now_utc: dt.datetime,
    current_place: Place,
    out_dir: str | Path,
    settings: Settings = MODERN,
) -> Path:
    """Write the complete dossier; returns its directory path."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    eph = default_ephemeris()

    natal_m, natal = _natal(subject, settings)
    now = from_utc(now_utc, current_place)
    name = subject.name
    files: dict[str, str] = {}

    # ---- natal (modern + hellenistic view) ---------------------------------
    hour = None if natal.settings.unknown_time else planetary_hour(natal_m)
    targets = {k: natal.points[k].lon for k in natal.points}
    if natal.angles:
        targets |= {a: natal.angles[a] for a in ("ASC", "MC")}
    stars = star_hits(natal_m.jd_ut, targets, natal.settings.fixed_star_orb)
    files["10_natal.txt"] = render_chart(natal, name, hour, stars)

    hell_settings = HELLENISTIC.with_(unknown_time=natal.settings.unknown_time)
    hell = compute_chart(natal_m, hell_settings, eph, kind="natal-hellenistic")
    files["11_natal_hellenistic.txt"] = render_chart(hell, name)

    # ---- timed layers --------------------------------------------------------
    files["20_transits.txt"] = render_transits(compute_transits(natal, now), name)
    files["21_secondary.txt"] = render_progressed(
        compute_progressed(natal, now, "secondary"), name)
    files["22_tertiary.txt"] = render_progressed(
        compute_progressed(natal, now, "tertiary"), name)
    files["23_solar_arc.txt"] = render_solar_arc(
        compute_solar_arc(natal, now), name)
    files["30_solar_return.txt"] = render_return(
        compute_return(natal, now, "SUN"), name)
    files["31_lunar_return.txt"] = render_return(
        compute_return(natal, now, "MOON"), name)
    if natal.is_day is not None:
        files["40_firdaria.txt"] = render_firdaria(firdaria(natal), natal, name)
    if natal.angles is not None:
        files["41_profections.txt"] = render_profections(
            profections(natal, now), name)

    # ---- meta + index ---------------------------------------------------------
    meta: list[str] = ["== ASTROTEXT DOSSIER-META v0 =="]
    meta.append(f"subject={name}")
    meta.append(f"engine=astrotext {__version__} | swisseph {eph.se_version} "
                f"| ephe {eph.info()['ephe_files']}")
    meta.append(f"birth-input={subject.local.isoformat(sep=' ')} "
                f"calendar={subject.calendar} fold={subject.fold} "
                f"unknown-time={str(subject.unknown_time).lower()}")
    meta.append(f"birth-resolved={natal_m.describe()}")
    meta.append(f"now-utc={now_utc.strftime('%Y-%m-%d %H:%M:%S')} "
                f"jd-ut={now.jd_ut:.8f}")
    meta.append(f"current-place={current_place.label()} "
                f"(used for: transit houses, return charts)")
    for line in natal.settings.describe():
        meta.append(f"set:{line}")
    for fl in natal.flags:
        meta.append(f"warning={fl}")
    if not natal.flags:
        meta.append("warning=(none)")
    meta.append("")
    meta.append(render_glossary().rstrip("\n"))
    meta.append("")
    meta.append("== END ==")
    files["00_meta.txt"] = "\n".join(meta) + "\n"

    idx: list[str] = ["== ASTROTEXT DOSSIER-INDEX v0 =="]
    idx.append(f"subject={name}")
    idx.append("format=docs/FORMAT.md | every file ends with '== END ==' "
               "(discard truncated files)")
    idx.append("")
    idx.append("-- READING ORDER (for interpreting agents) --")
    guide = {
        "00_meta.txt": "inputs, settings, warnings, EN->ZH glossary — read FIRST; "
                       "surface any warning= lines to the user",
        "10_natal.txt": "the base chart: points/houses/aspects/dignities/lots/stars",
        "11_natal_hellenistic.txt": "same instant, whole-sign + classical seven view",
        "20_transits.txt": "sky now vs natal; every hit lists exact timestamps; "
                           "Moon void-of-course status",
        "21_secondary.txt": "secondary progressions (1 day = 1 year) + progressed angles",
        "22_tertiary.txt": "tertiary progressions (1 day = 1 month)",
        "23_solar_arc.txt": "solar-arc directed positions + hits on natal",
        "30_solar_return.txt": "active solar return chart (cast at current place)",
        "31_lunar_return.txt": "active lunar return chart (cast at current place)",
        "40_firdaria.txt": "Persian time-lords, 75y majors + subs, dates",
        "41_profections.txt": "annual/monthly profections, year lord, full table",
    }
    for fname, desc in guide.items():
        if fname in files:
            idx.append(f"{fname} | {desc}")
    idx.append("")
    idx.append("-- INTERPRETATION CONTRACT --")
    idx.append("all numbers are precomputed; do not re-derive positions or orbs")
    idx.append("orb column is SIGNED separation-minus-exact; A=applying S=separating")
    idx.append("timestamps are UTC (Z); convert for the reader's locale if needed")
    idx.append("")
    idx.append("== END ==")
    files["index.txt"] = "\n".join(idx) + "\n"

    for fname, text in files.items():
        (out / fname).write_text(text, encoding="utf-8")
    return out
