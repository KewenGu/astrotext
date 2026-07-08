"""Renderers for the Vedic layer (files 50/51/52). Same line grammar."""
from __future__ import annotations

from ..core.zodiac import SIGNS_ABBR
from ..techniques.vedic.nakshatra import Nakshatra
from ..techniques.vedic.sidereal import GRAHA_ORDER, VedicChart
from ..techniques.vedic.vargas import VARGA_NAMES, vargottama
from ..techniques.vedic.vimshottari import DASHA_YEARS, DashaPeriod
from .text import FORMAT_VERSION
from .timed import jd_to_iso

__all__ = ["render_vedic_rashi", "render_vargas", "render_vimshottari"]

_GRAHA_ZH_SHORT = {"RAHU": "Rahu", "KETU": "Ketu"}


def _sid_dms(lon: float) -> str:
    from .text import dms
    return dms(lon)


def _meta(vc: VedicChart, kind: str, subject: str | None) -> list[str]:
    m = vc.moment
    L = [f"== ASTROTEXT {kind} {FORMAT_VERSION} =="]
    if subject:
        L.append(f"subject={subject}")
    L.append(f"local={m.local.isoformat(sep=' ')} calendar={m.calendar}")
    L.append(f"place={m.place.label()} tz={m.tz_used}")
    L.append(f"utc={m.utc.strftime('%Y-%m-%d %H:%M:%S')} jd-ut={m.jd_ut:.8f}")
    L.append(f"ayanamsa-value={vc.ayanamsa_value:.6f}")
    for line in vc.settings.describe():
        L.append(f"set:{line}")
    if vc.flags:
        for fl in vc.flags:
            L.append(f"warning={fl}")
    else:
        L.append("warning=(none)")
    return L


def _nak_label(nak: Nakshatra) -> str:
    return f"{nak.name}-{nak.pada}"


def render_vedic_rashi(vc: VedicChart, subject: str | None = None) -> str:
    L = _meta(vc, "VEDIC-RASHI", subject)

    L.append("")
    L.append("-- GRAHAS (sidereal) --")
    L.append("# graha | position | house | nakshatra-pada | nak-lord | lon | speed | tags")
    for k in GRAHA_ORDER:
        g = vc.grahas[k]
        tags = "R" if g.retrograde and k not in ("RAHU", "KETU") else (
            "R(always)" if k in ("RAHU", "KETU") else "-")
        house = f"H{g.house}" if g.house else "-"
        L.append(f"{k} | {_sid_dms(g.lon)} | {house} | {_nak_label(g.nak)} | "
                 f"{g.nak.lord} | {g.lon:.6f} | {g.lon_speed:+.6f} | {tags}")

    if vc.lagna is not None:
        L.append("")
        L.append("-- LAGNA & BHAVAS (whole sign) --")
        L.append(f"LAGNA | {_sid_dms(vc.lagna)} | {vc.lagna:.6f} | "
                 f"{_nak_label(vc.lagna_nak)} | {vc.lagna_nak.lord}")
        for h in range(1, 13):
            s = (vc.lagna_sign + h - 1) % 12
            occupants = ",".join(k for k in GRAHA_ORDER
                                 if vc.grahas[k].house == h) or "-"
            L.append(f"H{h} | {SIGNS_ABBR[s]} | {occupants}")

    L.append("")
    L.append("-- PANCHANGA --")
    p = vc.panchanga
    L.append(f"tithi={p.tithi} (no.{p.tithi_index + 1}, {p.tithi_fraction:.1%} elapsed) | "
             f"paksha={p.paksha}")
    L.append(f"karana={p.karana} (no.{p.karana_index + 1}) | yoga={p.yoga} "
             f"(no.{p.yoga_index + 1})")
    L.append(f"moon-nakshatra={_nak_label(vc.grahas['MOON'].nak)} | "
             f"lord={vc.grahas['MOON'].nak.lord}")

    L.append("")
    L.append(f"-- CHARA KARAKAS ({vc.settings.karaka_scheme}-scheme) --")
    L.append("# karaka | graha | advancement-deg (Rahu reversed)")
    for name, graha, deg in vc.karakas:
        L.append(f"{name} | {graha} | {deg:.4f}")

    L.append("")
    L.append("-- GRAHA DRISHTI (whole-sign; 7th all, Mars 4/8, Jup 5/9, Sat 3/10) --")
    L.append("# graha | aspected-signs | grahas-in-them")
    for g, d in vc.drishti.items():
        signs = ",".join(SIGNS_ABBR[s] for s in d["signs"])
        hit = ",".join(d["grahas"]) or "-"
        L.append(f"{g} | {signs} | {hit}")

    L.append("")
    L.append("== END ==")
    return "\n".join(L) + "\n"


def render_vargas(vc: VedicChart, table: dict[str, dict[int, int]],
                  subject: str | None = None) -> str:
    vargas = vc.settings.vargas
    L = _meta(vc, "VEDIC-VARGAS", subject)
    L.append("")
    L.append("-- DIVISIONAL CHART MATRIX (cell = sign in D<n>) --")
    L.append("# rules per varga: docs/TECHNIQUES.md (BPHS); VG = vargottama (D1==D9)")
    header = "graha | " + " | ".join(f"D{d}" for d in vargas)
    L.append(f"# {header}")
    rows = [k for k in list(table) if k != "LAGNA"] + (
        ["LAGNA"] if "LAGNA" in table else [])
    for k in rows:
        cells = " | ".join(SIGNS_ABBR[table[k][d]] for d in vargas)
        vg = ""
        if 1 in table[k] and 9 in table[k] and table[k][1] == table[k][9]:
            vg = " | VG"
        L.append(f"{k} | {cells}{vg}")
    L.append("")
    L.append("== END ==")
    return "\n".join(L) + "\n"


def render_vimshottari(periods: list[DashaPeriod], vc: VedicChart,
                       now_jd: float | None = None,
                       subject: str | None = None) -> str:
    L = _meta(vc, "VEDIC-VIMSHOTTARI", subject)
    birth = vc.moment.jd_ut
    moon_nak = vc.grahas["MOON"].nak
    first = periods[0]
    balance_days = first.end_jd - birth
    L.append(f"moon-nakshatra={moon_nak.name}-{moon_nak.pada} lord={moon_nak.lord}")
    L.append(f"balance-at-birth={balance_days / vc.settings.dasha_year_days:.4f}y "
             f"of {first.lord} mahadasha")
    if now_jd is not None:
        lineage = " > ".join(p.lord for p in periods
                             if p.start_jd <= now_jd < p.end_jd)
        L.append(f"current={lineage} (as of {jd_to_iso(now_jd)})")
    L.append("# level indent: MAHA / two-space antar / four-space pratyantar")
    L.append("# lord | start..end | age-span (negative = before birth)")

    ylen = vc.settings.dasha_year_days
    L.append("")
    L.append("-- VIMSHOTTARI TIMELINE --")
    for p in periods:
        a0 = (p.start_jd - birth) / ylen
        a1 = (p.end_jd - birth) / ylen
        dates = f"{jd_to_iso(p.start_jd)[:10]} .. {jd_to_iso(p.end_jd)[:10]}"
        mark = ""
        if now_jd is not None and p.start_jd <= now_jd < p.end_jd:
            mark = " <== now" if p.level == 3 else " <=="
        if p.level == 1:
            L.append(f"MAHA {p.lord} | {dates} | {a0:.2f}..{a1:.2f}{mark}")
        elif p.level == 2:
            L.append(f"  {p.lords[0]}/{p.lord} | {dates} | {a0:.2f}..{a1:.2f}{mark}")
        else:
            L.append(f"    {p.lords[0]}/{p.lords[1]}/{p.lord} | {dates} | "
                     f"{a0:.2f}..{a1:.2f}{mark}")
    L.append("")
    L.append("== END ==")
    return "\n".join(L) + "\n"
