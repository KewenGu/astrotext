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

__all__ = ["Subject", "build_dossier", "generate_dossier"]


@dataclass(frozen=True)
class Subject:
    name: str
    local: dt.datetime              # naive birth clock time
    place: Place
    tz: str | None = None           # override place.tz
    calendar: str = "gregorian"
    fold: int = 0
    unknown_time: bool = False
    notes: tuple[str, ...] = ()     # e.g. gazetteer resolution flags


def _natal(subject: Subject, settings: Settings) -> tuple[Moment, Chart]:
    if subject.unknown_time:
        settings = settings.with_(unknown_time=True)
    m = resolve(subject.local, subject.place, tz=subject.tz,
                calendar=subject.calendar, fold=subject.fold)
    return m, compute_chart(m, settings)


def build_dossier(
    subject: Subject,
    now_utc: dt.datetime,
    current_place: Place,
    settings: Settings = MODERN,
    fmt: str = "both",
    vedic_settings=None,
    tech=None,
) -> dict[str, str]:
    """Compute the complete dossier as {filename: content} without touching
    the filesystem — the shared engine behind the CLI writer and the MCP
    server.

    fmt: 'text' | 'json' | 'both'.  Text is the LLM-context view (compact,
    astrologese); JSON is the pipeline view (full float precision, standard
    tooling).  Both render from the same computed objects.
    """
    if fmt not in ("text", "json", "both"):
        raise ValueError("fmt must be 'text', 'json', or 'both'")
    from .options import TechOptions
    tech = tech or TechOptions()
    want_text = fmt in ("text", "both")
    want_json = fmt in ("json", "both")
    eph = default_ephemeris()

    from .render import json_out as J

    natal_m, natal = _natal(subject, settings)
    now = from_utc(now_utc, current_place)
    name = subject.name
    files: dict[str, str] = {}

    def emit(stem: str, text: str | None, jdict: dict | None) -> None:
        if want_text and text is not None:
            files[f"{stem}.txt"] = text
        if want_json and jdict is not None:
            files[f"{stem}.json"] = J.to_json(jdict)

    # ---- natal (modern + hellenistic view) ---------------------------------
    hour = None if natal.settings.unknown_time else planetary_hour(natal_m)
    targets = {k: natal.points[k].lon for k in natal.points}
    if natal.angles:
        targets |= {a: natal.angles[a] for a in ("ASC", "MC")}
    stars = star_hits(natal_m.jd_ut, targets, natal.settings.fixed_star_orb)
    emit("10_natal", render_chart(natal, name, hour, stars),
         J.chart_to_dict(natal, name, hour, stars))

    hell_settings = HELLENISTIC.with_(unknown_time=natal.settings.unknown_time)
    hell = compute_chart(natal_m, hell_settings, eph, kind="natal-hellenistic")
    emit("11_natal_hellenistic", render_chart(hell, name),
         J.chart_to_dict(hell, name))

    # ---- timed layers --------------------------------------------------------
    tr = compute_transits(natal, now, orb=tech.transit_orb,
                          window_days=tech.transit_window_days)
    emit("20_transits", render_transits(tr, name), J.transits_to_dict(tr, name))
    sec = compute_progressed(natal, now, "secondary",
                             year=tech.progression_year,
                             month=tech.progression_month)
    emit("21_secondary", render_progressed(sec, name),
         J.progressed_to_dict(sec, name))
    ter = compute_progressed(natal, now, "tertiary",
                             year=tech.progression_year,
                             month=tech.progression_month)
    emit("22_tertiary", render_progressed(ter, name),
         J.progressed_to_dict(ter, name))
    sa = compute_solar_arc(natal, now, year=tech.progression_year)
    emit("23_solar_arc", render_solar_arc(sa, name), J.solar_arc_to_dict(sa, name))
    sr = compute_return(natal, now, "SUN", precessed=tech.return_precessed)
    emit("30_solar_return", render_return(sr, name), J.return_to_dict(sr, name))
    lr = compute_return(natal, now, "MOON", precessed=tech.return_precessed)
    emit("31_lunar_return", render_return(lr, name), J.return_to_dict(lr, name))
    if natal.is_day is not None:
        fd = firdaria(natal, nodes=tech.firdaria_nodes)
        emit("40_firdaria",
             render_firdaria(fd, natal, name, nodes=tech.firdaria_nodes),
             J.firdaria_to_dict(fd, natal, name))
    if natal.angles is not None:
        pf = profections(natal, now)
        emit("41_profections", render_profections(pf, name),
             J.profections_to_dict(pf, name))

    # ---- vedic layer -----------------------------------------------------------
    from .render.vedic import (
        render_vargas, render_vedic_rashi, render_vimshottari,
    )
    from .techniques.vedic import compute_vedic_chart, varga_table, vimshottari

    vc = compute_vedic_chart(natal_m, vedic_settings,
                             unknown_time=natal.settings.unknown_time)
    emit("50_vedic_rashi", render_vedic_rashi(vc, name),
         J.vedic_chart_to_dict(vc, name))
    vlons = {k: vc.grahas[k].lon for k in vc.grahas}
    if vc.lagna is not None:
        vlons["LAGNA"] = vc.lagna
    vtable = varga_table(vlons, vc.settings.vargas)
    emit("51_vedic_vargas", render_vargas(vc, vtable, name),
         J.vargas_to_dict(vc, vtable, name))
    vd = vimshottari(vc.grahas["MOON"].lon, natal_m.jd_ut,
                     vc.settings.dasha_year_days,
                     max_level=tech.dasha_max_level)
    emit("52_vedic_vimshottari", render_vimshottari(vd, vc, now.jd_ut, name),
         J.vimshottari_to_dict(vd, vc, now.jd_ut, name))

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
    for note in subject.notes:
        meta.append(f"warning={note}")
    for fl in natal.flags:
        meta.append(f"warning={fl}")
    if not (natal.flags or subject.notes):
        meta.append("warning=(none)")
    meta.append("")
    meta.append(render_glossary().rstrip("\n"))
    meta.append("")
    meta.append("== END ==")
    files["00_meta.txt"] = "\n".join(meta) + "\n"

    idx: list[str] = ["== ASTROTEXT DOSSIER-INDEX v0 =="]
    idx.append(f"subject={name}")
    idx.append(f"formats={fmt} | text: docs/FORMAT.md, ends '== END ==' "
               f"(discard truncated) | json: same data, full float precision")
    idx.append("")
    idx.append("-- READING ORDER (for interpreting agents) --")
    guide = {
        "00_meta": "inputs, settings, warnings, EN->ZH glossary — read FIRST; "
                   "surface any warning= lines to the user",
        "10_natal": "the base chart: points/houses/aspects/dignities/lots/stars",
        "11_natal_hellenistic": "same instant, whole-sign + classical seven view",
        "20_transits": "sky now vs natal; every hit lists exact timestamps; "
                       "Moon void-of-course status",
        "21_secondary": "secondary progressions (1 day = 1 year) + progressed angles",
        "22_tertiary": "tertiary progressions (1 day = 1 month)",
        "23_solar_arc": "solar-arc directed positions + hits on natal",
        "30_solar_return": "active solar return chart (cast at current place)",
        "31_lunar_return": "active lunar return chart (cast at current place)",
        "40_firdaria": "Persian time-lords, 75y majors + subs, dates",
        "41_profections": "annual/monthly profections, year lord, full table",
        "50_vedic_rashi": "sidereal D1: grahas/nakshatras/Lagna/whole-sign "
                          "bhavas/panchanga/karakas/drishti",
        "51_vedic_vargas": "all 16 divisional charts as a sign matrix (+VG)",
        "52_vedic_vimshottari": "120y dasha timeline, 3 levels, current marked",
    }
    for stem, desc in guide.items():
        exts = [e for e in (".txt", ".json") if f"{stem}{e}" in files]
        if exts:
            line = f"{stem}{exts[0]} | {desc}"
            if len(exts) > 1:
                line += f" | also: {stem}{exts[1]}"
            idx.append(line)
    idx.append("")
    idx.append("-- INTERPRETATION CONTRACT --")
    idx.append("all numbers are precomputed; do not re-derive positions or orbs")
    idx.append("orb column is SIGNED separation-minus-exact; A=applying S=separating")
    idx.append("timestamps are UTC (Z); convert for the reader's locale if needed")
    idx.append("")
    idx.append("== END ==")
    files["index.txt"] = "\n".join(idx) + "\n"

    return files


def generate_dossier(
    subject: Subject,
    now_utc: dt.datetime,
    current_place: Place,
    out_dir: str | Path,
    settings: Settings = MODERN,
    fmt: str = "both",
    vedic_settings=None,
    tech=None,
) -> Path:
    """Write the complete dossier; returns its directory path."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = build_dossier(subject, now_utc, current_place, settings, fmt,
                          vedic_settings, tech)
    for fname, text in files.items():
        (out / fname).write_text(text, encoding="utf-8")
    return out
