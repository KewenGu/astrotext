"""JSON renderer — the machine-facing view of the same data model.

Division of labor (docs/FORMAT.md):
  * text v0  — the LLM-context format: token-lean, astrologese-native,
               human-checkable. PRIMARY for interpretation agents.
  * json v0  — the pipeline format: standard tooling, schema-checkable,
               FULL float precision (text is display-rounded; JSON carries
               the raw doubles). PRIMARY for code, storage, RAG indexing.

Both render from the same objects; neither is derived from the other.
Determinism: sorted keys, compact separators, repr-exact floats.
"""
from __future__ import annotations

import json
from typing import Any

from .. import __version__
from ..core.chart import Chart
from ..core.hours import PlanetaryHour
from ..core.stars import StarHit

__all__ = ["chart_to_dict", "to_json", "transits_to_dict", "progressed_to_dict",
           "solar_arc_to_dict", "return_to_dict", "firdaria_to_dict",
           "profections_to_dict"]

_ENVELOPE = {"format": "astrotext-json", "format_version": 0}


def _moment(m) -> dict[str, Any]:
    return {
        "local": m.local.isoformat(sep=" "),
        "calendar": m.calendar,
        "place": {"name": m.place.name, "lat": m.place.lat, "lon": m.place.lon,
                  "tz": m.place.tz, "elevation_m": m.place.elevation_m},
        "tz_used": m.tz_used,
        "utc_offset_sec": m.utc_offset.total_seconds(),
        "utc": m.utc.isoformat(sep=" "),
        "jd_ut": m.jd_ut, "jd_tt": m.jd_tt, "delta_t_sec": m.delta_t_sec,
        "flags": list(m.flags),
    }


def _aspect_hit(h) -> dict[str, Any]:
    return {"p1": h.p1, "p2": h.p2, "aspect": h.aspect.key,
            "abbr": h.aspect.abbr, "angle": h.aspect.angle,
            "separation": h.separation, "orb_signed": h.orb_signed,
            "orb_abs": h.orb_abs, "orb_allowed": h.orb_allowed,
            "phase": h.phase}


def chart_to_dict(chart: Chart, subject: str | None = None,
                  hour: PlanetaryHour | None = None,
                  stars: list[StarHit] | None = None,
                  extra: dict[str, Any] | None = None) -> dict[str, Any]:
    d: dict[str, Any] = dict(_ENVELOPE)
    d["engine"] = f"astrotext {__version__}"
    d["kind"] = chart.kind
    if subject:
        d["subject"] = subject
    if extra:
        d["context"] = extra
    d["moment"] = _moment(chart.moment)
    d["settings"] = {line.split("=", 1)[0]: line.split("=", 1)[1]
                     for line in chart.settings.describe()}
    d["obliquity"] = chart.obliquity
    d["house_system_used"] = chart.house_system_used
    d["sect"] = {"is_day": chart.is_day, "sun_altitude": chart.sun_altitude}
    d["warnings"] = list(chart.flags)

    d["points"] = {
        k: {"lon": p.lon, "lat": p.lat, "dist_au": p.dist_au,
            "lon_speed": p.lon_speed, "dec": p.dec,
            "retrograde": p.retrograde, "oob": p.oob,
            "sign": p.sign, "sign_deg": p.sign_deg, "house": p.house}
        for k, p in chart.points.items()
    }
    d["angles"] = chart.angles
    d["cusps"] = list(chart.cusps) if chart.cusps else None
    d["aspects"] = [_aspect_hit(h) for h in chart.aspects]
    d["dignities"] = {
        k: {"dignities": list(r.dignities), "score": r.score,
            "peregrine": r.peregrine, "sign_ruler": r.sign_ruler,
            "exalted_here": r.exalted_here,
            "triplicity_rulers": list(r.triplicity_rulers),
            "bound_ruler": r.bound_ruler, "decan_ruler": r.decan_ruler}
        for k, r in chart.dignities.items()
    }
    d["receptions"] = [{"a": a, "b": b, "kind": kind}
                       for a, b, kind in chart.receptions]
    d["dispositors"] = chart.dispositors
    d["lots"] = chart.lots
    d["moon"] = {"elongation": chart.moon.elongation, "phase": chart.moon.phase,
                 "waxing": chart.moon.waxing,
                 "illumination": chart.moon.illumination}
    d["antiscia"] = [{"p1": p1, "kind": kind, "p2": p2, "delta": delta}
                     for p1, kind, p2, delta in chart.antiscia]
    if stars is not None:
        d["fixed_stars"] = [{"star": s.star, "star_lon": s.star_lon,
                             "target": s.target, "delta": s.delta}
                            for s in stars]
    if hour is not None:
        d["planetary_hour"] = {
            "polar": hour.polar, "day_ruler": hour.day_ruler,
            "weekday": hour.weekday, "hour_ruler": hour.hour_ruler,
            "hour_no": hour.hour_no, "is_day_hour": hour.is_day_hour,
            "sunrise_jd": hour.sunrise_jd, "sunset_jd": hour.sunset_jd,
            "next_sunrise_jd": hour.next_sunrise_jd}
    return d


def transits_to_dict(rep, subject: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = dict(_ENVELOPE)
    d["kind"] = "transits"
    if subject:
        d["subject"] = subject
    d["moment"] = _moment(rep.sky.moment)
    d["natal_jd_ut"] = rep.natal.moment.jd_ut
    d["orb"] = rep.orb
    d["window_days"] = rep.window_days
    d["points"] = {
        k: {"lon": rep.sky.points[k].lon, "lon_speed": rep.sky.points[k].lon_speed,
            "retrograde": rep.sky.points[k].retrograde,
            "natal_house": rep.natal_wheel_houses.get(k),
            "sky_house": rep.sky.points[k].house}
        for k in rep.natal_wheel_houses
    }
    d["hits"] = [{"t_point": h.t_point, "aspect": h.aspect.key,
                  "angle": h.aspect.angle, "n_point": h.n_point,
                  "n_lon": h.n_lon, "separation": h.separation,
                  "orb_signed": h.orb_signed, "phase": h.phase,
                  "exact_jds": list(h.exact_jds)} for h in rep.hits]
    if rep.moon_void is not None:
        v = rep.moon_void
        d["moon_void"] = {
            "is_void": v.is_void, "moon_sign": v.moon_sign,
            "sign_exit_jd": v.sign_exit_jd,
            "last_exact": list(v.last_exact) if v.last_exact else None,
            "next_exact": list(v.next_exact) if v.next_exact else None,
            "next_is_after_sign_change": v.next_is_after_sign_change}
    d["warnings"] = list(rep.sky.flags)
    return d


def progressed_to_dict(rep, subject: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = dict(_ENVELOPE)
    d["kind"] = f"{rep.kind}-progressed"
    if subject:
        d["subject"] = subject
    d["natal_jd_ut"] = rep.natal.moment.jd_ut
    d["target_jd_ut"] = rep.target_jd_ut
    d["prog_jd_ut"] = rep.prog_jd_ut
    d["age_years"] = rep.age_years
    d["clock"] = rep.clock
    d["points"] = {
        k: {"lon": p.lon, "lon_speed": p.lon_speed, "retrograde": p.retrograde,
            "natal_house": rep.natal_wheel_houses.get(k)}
        for k, p in rep.chart.points.items()}
    if rep.angles_sa is not None:
        d["angles_solar_arc_mc"] = {
            "method": rep.angles_sa.method, "mc": rep.angles_sa.mc,
            "asc": rep.angles_sa.asc, "armc": rep.angles_sa.armc,
            "cusps": list(rep.angles_sa.cusps)}
    d["angles_quotidian"] = rep.chart.angles
    d["hits"] = [_aspect_hit(h) for h in rep.hits]
    d["warnings"] = list(rep.chart.flags)
    return d


def solar_arc_to_dict(rep, subject: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = dict(_ENVELOPE)
    d["kind"] = "solar-arc"
    if subject:
        d["subject"] = subject
    d["natal_jd_ut"] = rep.natal.moment.jd_ut
    d["target_jd_ut"] = rep.target_jd_ut
    d["arc"] = rep.arc
    d["year"] = rep.year
    d["directed"] = rep.directed
    d["hits"] = [_aspect_hit(h) for h in rep.hits]
    return d


def return_to_dict(rep, subject: str | None = None) -> dict[str, Any]:
    d = chart_to_dict(rep.chart, subject, extra={
        "return_of": rep.body, "natal_lon_used": rep.natal_lon_used,
        "precessed": rep.precessed, "active_jd": rep.active_jd,
        "next_jd": rep.next_jd, "residual_deg": rep.residual_deg,
        "natal_jd_ut": rep.natal.moment.jd_ut,
        "cast_at": {"name": rep.location.name, "lat": rep.location.lat,
                    "lon": rep.location.lon}})
    return d


def firdaria_to_dict(periods, natal, subject: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = dict(_ENVELOPE)
    d["kind"] = "firdaria"
    if subject:
        d["subject"] = subject
    d["natal_jd_ut"] = natal.moment.jd_ut
    d["is_day"] = natal.is_day
    d["periods"] = [{"level": p.level, "lord": p.lord,
                     "major_lord": p.major_lord,
                     "start_jd": p.start_jd, "end_jd": p.end_jd,
                     "start_age": p.start_age, "end_age": p.end_age}
                    for p in periods]
    return d


def profections_to_dict(rep, subject: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = dict(_ENVELOPE)
    d["kind"] = "profections"
    if subject:
        d["subject"] = subject
    d["natal_jd_ut"] = rep.natal.moment.jd_ut
    d["years"] = [{"age": y.age, "start_jd": y.start_jd, "end_jd": y.end_jd,
                   "asc_sign": y.asc_sign, "year_lord": y.year_lord}
                  for y in rep.years]
    d["current"] = ({"age": rep.current.age,
                     "month_index": rep.current_month_index,
                     "month_sign": rep.current_month_sign,
                     "month_lord": rep.current_month_lord,
                     "profected_mc_sign": rep.profected_mc_sign,
                     "profected_fortune_sign": rep.profected_fortune_sign}
                    if rep.current else None)
    return d


def to_json(d: dict[str, Any]) -> str:
    """Deterministic JSON: sorted keys, compact separators, exact floats."""
    return json.dumps(d, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n"


# ---- vedic layer -------------------------------------------------------------

def _nak_dict(n) -> dict[str, Any]:
    return {"index": n.index, "name": n.name, "pada": n.pada,
            "lord": n.lord, "deg_in_nak": n.deg_in_nak, "fraction": n.fraction}


def vedic_chart_to_dict(vc, subject: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = dict(_ENVELOPE)
    d["kind"] = "vedic-rashi"
    if subject:
        d["subject"] = subject
    d["moment"] = _moment(vc.moment)
    d["settings"] = {line.split("=", 1)[0]: line.split("=", 1)[1]
                     for line in vc.settings.describe()}
    d["ayanamsa_value"] = vc.ayanamsa_value
    d["warnings"] = list(vc.flags)
    d["grahas"] = {
        k: {"lon": g.lon, "lat": g.lat, "lon_speed": g.lon_speed,
            "retrograde": g.retrograde, "sign": g.sign, "sign_deg": g.sign_deg,
            "house": g.house, "nakshatra": _nak_dict(g.nak)}
        for k, g in vc.grahas.items()
    }
    d["lagna"] = ({"lon": vc.lagna, "sign": vc.lagna_sign,
                   "nakshatra": _nak_dict(vc.lagna_nak)}
                  if vc.lagna is not None else None)
    p = vc.panchanga
    d["panchanga"] = {"tithi_index": p.tithi_index, "tithi": p.tithi,
                      "paksha": p.paksha, "tithi_fraction": p.tithi_fraction,
                      "karana_index": p.karana_index, "karana": p.karana,
                      "yoga_index": p.yoga_index, "yoga": p.yoga}
    d["karakas"] = [{"karaka": k, "graha": g, "advancement": a}
                    for k, g, a in vc.karakas]
    d["drishti"] = vc.drishti
    return d


def vargas_to_dict(vc, table, subject: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = dict(_ENVELOPE)
    d["kind"] = "vedic-vargas"
    if subject:
        d["subject"] = subject
    d["natal_jd_ut"] = vc.moment.jd_ut
    d["ayanamsa_value"] = vc.ayanamsa_value
    d["vargas"] = list(vc.settings.vargas)
    d["signs"] = {g: {f"D{dv}": s for dv, s in row.items()}
                  for g, row in table.items()}
    d["vargottama"] = sorted(g for g, row in table.items()
                             if 1 in row and 9 in row and row[1] == row[9])
    return d


def vimshottari_to_dict(periods, vc, now_jd: float | None = None,
                        subject: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = dict(_ENVELOPE)
    d["kind"] = "vedic-vimshottari"
    if subject:
        d["subject"] = subject
    d["natal_jd_ut"] = vc.moment.jd_ut
    d["moon_nakshatra"] = _nak_dict(vc.grahas["MOON"].nak)
    d["dasha_year_days"] = vc.settings.dasha_year_days
    if now_jd is not None:
        d["now_jd_ut"] = now_jd
        d["current_lineage"] = [p.lord for p in periods
                                if p.start_jd <= now_jd < p.end_jd]
    d["periods"] = [{"level": p.level, "lords": list(p.lords),
                     "start_jd": p.start_jd, "end_jd": p.end_jd}
                    for p in periods]
    return d
