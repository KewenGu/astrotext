# AstroText

**Plain-text astrology chart engine for AI agents.** Given a birth moment + birth place (+ current location), it generates a complete, verifiable, deterministic "astrological dossier" — a directory of plain-text files covering natal, transits, progressions (secondary/tertiary), solar arc, solar/lunar returns, firdaria, profections, and (phase 2) Vedic charts — designed to be read by interpreting LLM agents.

## Design axioms (first principles)

1. **AI agents cannot do arithmetic.** Every number an interpreter needs is precomputed: aspect orbs, applying/separating, next-exact timestamps, dignity scores, receptions, dispositor chains, sect. The text leaves no arithmetic to the reader.
2. **Every technique is a pure function of three base facts**: ephemeris positions, time conversion (local → UT → TT/ΔT), and coordinates/houses. The base layer is proven correct first; all charts are compositions.
3. **Error comes from timezones and geography, not astronomy.** Historical tz database, LMT fallback, and full echo of resolved inputs in every dossier header.
4. **Correctness is proven by comparison and invariants, never by eyeballing.** Bit-level agreement with `swetest` (the Swiss Ephemeris reference CLI), cross-source checks, and property-based tests.
5. **Reproducibility.** All settings (zodiac, houses, orbs, ΔT model, engine + ephemeris versions) are stamped into every output. Same input ⇒ byte-identical output.

## Engine core

[Swiss Ephemeris](https://www.astro.com/swisseph/) via `pyswisseph`, both **built from source** (this project runs in network-restricted environments; see `vendor/`). The same engine and data files power astro.com, so agreement with astro.com is a design target, not a coincidence.

> **License:** AGPL-3.0 (see LICENSE and NOTICE) — inherited from Swiss Ephemeris.
> Commercial closed-source distribution would require an Astrodienst license or an
> engine swap (the `ephem` layer isolates it).

## Layout

```
src/astrotext/
  ephem/       L0: Swiss Ephemeris wrapper (positions, speeds, declinations, ΔT)
  timespace/   L0: place → lat/lon → IANA tz → UT → JD; LMT fallback; DST-gap detection
  core/        L1: Chart(moment, place, settings) → planets, houses, angles, aspects
  techniques/  L2: transits, progressions, solar arc, returns, firdaria, profections, …
  profiles/    L3: modern / hellenistic / vedic setting presets
  render/      L4: compact text (primary), JSON (machine), round-trip parser, zh glossary
tests/         golden / properties / cross / edge
tools/         fetch & build scripts, verification report generator
docs/          FORMAT.md, TECHNIQUES.md (per-technique sources), PLAN.md
vendor/        pinned third-party sources (build scripts; not committed wholesale)
```

## Quick start

```bash
make vendor    # clone + build pyswisseph, swetest, ephemeris files, pytest (one-time)
make test      # full test suite
make verify    # regenerate verification_report.md against reference sources
```

## Status

M0 (foundation & risk removal) — in progress. See `docs/PLAN.md`.
