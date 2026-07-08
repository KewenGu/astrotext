# AstroText

**Plain-text astrology chart engine for AI agents.** Given a birth moment,
birth place (Chinese place names OK), and current location, it generates a
complete, verifiable, deterministic "astrological dossier" — a directory of
plain-text + JSON files designed to be read by interpreting LLM agents,
covering three traditions:

* **Modern Western** — natal (Placidus, full aspect engine with
  applying/separating, declinations, out-of-bounds, fixed stars), transits
  with every exact timestamp precomputed, secondary/tertiary progressions,
  solar arc, solar/lunar returns (precession-corrected option).
* **Classical/Hellenistic** — whole-sign view, sect, essential dignities
  (Egyptian bounds, Dorothean triplicities, Chaldean decans), receptions,
  dispositor chains, lots, antiscia, planetary hours, firdaria, annual
  profections with true solar-return year boundaries, Moon void-of-course.
* **Vedic (Jyotish)** — sidereal (Lahiri default, native Swiss Ephemeris
  mode), nakshatras + padas, panchanga, the full 16 Shodashavarga
  divisional charts, chara karakas, graha drishti, and a three-level
  Vimshottari dasha timeline (819 periods).

## Quick start

```bash
make vendor    # one-time: clone + build pyswisseph, swetest, ephemeris, pytest
make test      # 321 tests
make verify    # regenerate verification_report.md against reference sources

python3 -m astrotext dossier \
  --name "Sample" --birth "1988-06-15 14:30" --birth-place 北京 \
  --now "2026-07-08 12:00" --cur-place 纽约 --out ./dossiers
```

That command resolves both place names offline (170k GeoNames places with
Chinese aliases), applies the historical timezone database (including
China's 1986–91 DST), and writes 15 text files + 13 JSON siblings:

```
index.txt              how to read this dossier (the agent contract)
00_meta.txt            input echo, resolved time/place, settings, EN→ZH glossary
10_natal(.txt/.json)   11_natal_hellenistic   20_transits (+ Moon VOC)
21_secondary  22_tertiary  23_solar_arc
30_solar_return  31_lunar_return
40_firdaria  41_profections
50_vedic_rashi  51_vedic_vargas  52_vedic_vimshottari
```

## Four facades, one engine

Everything is a five-layer pure-function pipeline (see `docs/API.md`);
these are thin shells over the same `build_dossier()`:

| facade | entry | for |
|---|---|---|
| Python library | `astrotext.dossier.build_dossier(...)` | your own code |
| CLI | `python3 -m astrotext dossier\|verify\|mcp\|http` | shell / cron |
| MCP server (stdio) | `python3 -m astrotext mcp` | AI agents (3 tools) |
| HTTP | `python3 -m astrotext http` → `POST /v0/chart` | services |

All number-changing knobs (house system, node type, orbs, ayanamsa, dasha
depth, ...) are explicit settings — passable per request on REST/MCP,
strictly validated, and echoed into every output header.

## Design axioms

1. **AI agents cannot do arithmetic.** Every number an interpreter needs is
   precomputed: orbs, applying/separating, next-exact timestamps, dignity
   scores, dispositor chains. The text leaves no arithmetic to the reader.
2. **Every technique is a pure function of three base facts**: ephemeris
   positions, time conversion (local → UT → TT/ΔT), and coordinates/houses.
3. **Error comes from timezones and geography, not astronomy.** Historical
   tzdb, LMT fallback, DST-gap hard errors, and full echo of resolved
   inputs in every header.
4. **Correctness is proven by comparison and invariants, never by
   eyeballing** (see below).
5. **Reproducibility.** Same input ⇒ byte-identical output; all settings
   stamped into the files; text view canonicalized to be cross-platform
   stable at display precision.

## How it is verified

* **Bit-level agreement with `swetest`** — the Swiss Ephemeris reference
  CLI, compiled from Astrodienst's sources and driven as an independent
  process: planets, houses, angles, and sidereal positions agree to
  ≤ 5×10⁻⁸ ° across a 1800–2399 sample grid (`make verify` regenerates
  the report).
* **Adversarial table review** — independent subagents re-derived every
  classical and Vedic rule table (Egyptian bounds, triplicities, the 16
  varga mappings, dasha years, karakas, drishti) from the sources without
  seeing the code: zero mismatches; tradition variants documented as knobs.
* **Property invariants** — progressions collapse to the natal chart at
  age 0, solar arc ≡ progressed-Sun displacement, returns solve to < 0.1″,
  firdaria sums to 75y, vimshottari nests gaplessly to 120y, tropical −
  sidereal is one ayanamsa for every body, round-trip parsing reproduces
  every number.
* **Byte-frozen snapshots** — 20 golden charts (real AA-rated data +
  synthetic edge cases: polar fallback, DST gaps, LMT era, Julian calendar,
  unknown birth time) plus timed reports; any drift fails CI.

## Engine & data

[Swiss Ephemeris](https://www.astro.com/swisseph/) via `pyswisseph`, both
**built from pinned sources** by `tools/vendor.sh` (works in
network-restricted environments; recursive submodules handled — see the
macOS note in that script). Ephemeris data files (1800–2399) are committed
with provenance. Gazetteer compiled from GeoNames (CC-BY 4.0) by
`tools/build_gazetteer.py`; a curated zh-exonym supplement covers Chinese
names of world cities, every entry machine-verified.

> **License:** AGPL-3.0 (see LICENSE and NOTICE) — inherited from Swiss
> Ephemeris. Commercial closed-source distribution would require an
> Astrodienst license or an engine swap (the `ephem` layer isolates it).

## Docs

`docs/API.md` (facades & layers) · `docs/FORMAT.md` (the text/JSON format
contract) · `docs/TECHNIQUES.md` (every technique's convention, variants,
and sources) · `docs/PLAN.md` (architecture plan + session log).

## Status

v0 **feature-complete** across all three traditions (M0–M8b): engine,
dossier generator, gazetteer, MCP + HTTP facades, request-level settings.
Cross-platform validated (Linux/gcc and macOS/clang). Remaining before the
v1 format freeze: user acceptance spot-checks against astro.com and
drikpanchang.com.
