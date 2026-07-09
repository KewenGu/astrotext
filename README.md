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
* **Vedic (Jyotish)** — sidereal (Lahiri default, SE-parity ayanamsa),
  nakshatras + padas, panchanga, the full 16 Shodashavarga
  divisional charts, chara karakas, graha drishti, and a three-level
  Vimshottari dasha timeline (819 periods).

## Quick start

```bash
make vendor        # one-time: kernel deps (numpy/jplephem/pyerfa) + DE440 excerpt + pytest
make test          # full suite
make check-license # prove the default build ships no Swiss Ephemeris code/data

./astrotext dossier \
  --name "Sample" --birth "1988-06-15 14:30" --birth-place 北京 \
  --now "2026-07-08 12:00" --cur-place 纽约 --out ./dossiers
```

`./astrotext` is a zero-install launcher that wires the vendored module
paths (`src`, `vendor/py`, `vendor/lib`) and `SE_EPHE_PATH` before
dispatching to the CLI — nothing is installed into your Python. If you
prefer `python3 -m astrotext`, export those paths yourself. Note the C
extension is built per Python version: run `./astrotext` with the same
python (venv or not) that ran `make vendor`.

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
| CLI | `./astrotext dossier\|verify\|mcp\|http` | shell / cron |
| MCP server (stdio) | `./astrotext mcp` | AI agents (3 tools) |
| HTTP | `./astrotext http` → `POST /v0/chart` | services |

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

* **Three-way agreement (de440 vs `swetest` vs Skyfield)** — the `de440`
  kernel is checked module-by-module against the Swiss Ephemeris reference
  CLI *and* Skyfield on the same DE440, over a 1800–2399 sample grid, with
  measured and individually-attributed sub-arcsecond gates (planets ≤0.01″,
  houses/angles exact, sidereal ≤0.01″; documented drifts are the
  DE431→DE440 lunar term and newer Lilith/Chiron orbit solutions). See
  `docs/KERNEL.md`; `make vendor-swiss` then `make verify` regenerates the
  report.
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

Default backend **`de440`**: a clean-room computation core — the
[JPL DE440](https://ssd.jpl.nasa.gov/planets/eph_export.html) ephemeris
(public domain) read via `jplephem` (MIT), with
[ERFA](https://github.com/liberfa/pyerfa)/IAU-2006/2000A reductions
(BSD-3), plus the engine's own houses, sidereal, fixed-star (Hipparcos /
van Leeuwen 2007) and rise/set implementations. Permissively licensed end
to end; `tools/vendor.sh` fetches the DE440 excerpt and installs the
kernel deps. Accuracy is verified module-by-module against Swiss Ephemeris
with measured, attributed sub-arcsecond gates (see `docs/KERNEL.md`).

An optional `backend="swiss"` reference ([Swiss
Ephemeris](https://www.astro.com/swisseph/) via `pyswisseph`) is built
only by `make vendor-swiss` for cross-implementation verification; it is
**AGPL and never shipped** — no Swiss Ephemeris code or data is committed
or included in wheels (`make check-license` enforces this). Gazetteer
compiled from GeoNames (CC-BY 4.0) by `tools/build_gazetteer.py`; a
curated zh-exonym supplement covers Chinese names of world cities, every
entry machine-verified.

> **License:** Apache-2.0 (see LICENSE and NOTICE). The default
> distribution is permissively licensed and free to embed, host and
> commercialize; the AGPL Swiss Ephemeris is an optional dev/verify
> reference, isolated in the `ephem` layer and excluded from releases.

## Docs

`docs/API.md` (facades & layers) · `docs/FORMAT.md` (the text/JSON format
contract) · `docs/TECHNIQUES.md` (every technique's convention, variants,
and sources) · `docs/PLAN.md` (architecture plan + session log).

## Status

**v1 format frozen (2026-07-08); engine 2.0.0-rc1.** Feature-complete
across all three traditions (M0–M8b): engine, dossier generator,
gazetteer, MCP + HTTP facades, request-level settings. The default
backend is now the permissively-licensed `de440` kernel (K7 switchover);
golden snapshots regenerated with a fully-attributed diff (99.45%
byte-identical, DMS displays unchanged bar ±1" on Lilith/Chiron). UAT
cross-checks passed against astro.com (official hosted swetest:
planets/cusps/angles <= 0.1"), drikpanchang.com (panchanga to the
minute), vedicastrochart.com (grahas <= 0.4", vargas, vimshottari <= 1
day) and astro-seek. See CHANGELOG.md and docs/KERNEL.md.
