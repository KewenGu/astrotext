# Kernel v2 — replacing Swiss Ephemeris (plan & normative spec)

Status: PLANNED (K0 not started).  Owner doc for the V2 kernel swap.
Read with PLAN.md §V2 (milestones, in Chinese) and TECHNIQUES.md (which
stays kernel-agnostic).  Rule inherited from the house style: every
convention states its source; no hidden defaults; clean-room only.

## 1. Goal & non-goals

Goal: a **permissively-licensed computation core** (target: repo
relicenses AGPL-3.0 → Apache-2.0) with JPL-grade accuracy, so the
project can be embedded, hosted and commercialized freely and can serve
as provider infrastructure for AI agents.  Swiss Ephemeris (AGPL)
becomes an *optional, dev/verification-only* backend, off by default
and excluded from the shipped distribution.

Non-goals: no change to astrology semantics, technique conventions,
text/JSON **format v1** (frozen 2026-07-08), public Python API, CLI,
MCP or HTTP surfaces.  `Settings`/`VedicSettings` knobs keep their
meanings.  Engine version bumps to 2.0.0 when the default backend
flips.

## 2. Decision record

| option | license | precision | verdict |
|---|---|---|---|
| Astrodienst commercial license | proprietary (paid) | as today | cheapest short-term; keeps dependence — rejected as strategy |
| Moshier analytic (aa-56) | permissive | ~0.1" planets, worse Moon | dated; precision regression — rejected |
| Skyfield as production core | MIT | excellent | pure-python speed risk in root-finding loops — demoted to verification reference |
| **DE440 + jplephem + pyerfa, own reduction pipeline** | MIT / BSD-3 / public domain | ≥ SE (SE *is* compressed DE) | **chosen** |

Key fact: Swiss Ephemeris planetary files are a ~0.001" compression of
JPL DE ephemerides.  Reading DE440 directly and reducing with ERFA
(IAU-endorsed routines, BSD) reproduces — not approximates — the same
physics.  swetest remains the bit-reference during development; add
Skyfield as a second, independent reference: the verify harness
upgrades from "wrapper vs its own kernel" to a genuine three-way
cross-implementation check (ours vs Astrodienst vs Rhodes).

## 3. Dependencies & data (all permissive)

* `jplephem` (MIT) — SPK segment reader, numpy-native.
* `pyerfa` (BSD-3) — ERFA: precession-nutation, sidereal time, obliquity,
  proper motion; vectorized ufuncs over C.
* Data files, fetched by `tools/fetch_kernel_data.py` with pinned
  SHA-256, not committed:
  - `de440.bsp` excerpt **1799-01-01..2400-02-01** via
    `python -m jplephem excerpt` (~40 MB; full file is 114 MB,
    1550–2650) — covers the supported 1800–2399 span with margin.
  - Chiron (2060) SPK generated from JPL Horizons (public domain).
    Validity note: SE documents Chiron as reliable ~675 AD–4650 AD;
    our 1800–2399 span is safe.
  - Hipparcos (van Leeuwen 2007) astrometry for the 22 fixed stars in
    `core/stars.py` (ESA data, free with attribution).
  - Leap-second table + the ΔT tables named in §5 (IERS / published).

## 4. Reduction pipeline (normative)

Per body at TT instant t, geocentric apparent ecliptic-of-date —
matching SE's default `FLG_SWIEPH|FLG_SPEED` semantics:

1. Barycentric ICRF states of body and Earth from SPK (Moon: geocentric
   segment directly).
2. Light-time iteration on the geometric geocentric vector (2
   iterations; applies to the Moon too — its 1.3 s light-time moves
   lon ~0.7").
3. Annual aberration, relativistic formula (observer = Earth center).
4. Frame bias + precession + nutation to true equator/equinox of date:
   `erfa.pnm06a` (IAU 2006/2000A).
5. Equatorial→ecliptic of date with true obliquity
   (`erfa.obl06` + Δε from `erfa.nut06a`) → lon, lat.
6. RA/dec taken from step 4's vector; distance = light-time-corrected
   geometric distance (SE convention).
7. Speeds: central difference at ±0.5 h with the full pipeline at each
   sample (light-time-consistent); target error ≤ 1e-6 °/day.
   One bias-precession-nutation matrix is computed per *instant* and
   shared across bodies (dominant cost; see §10).

Sun = apparent geocentric Sun via the same steps.  Topocentric mode is
out of scope for v2 (engine never exposed it).

## 5. Time scales (parity-critical)

* UTC→TAI via leap table; TT = TAI + 32.184 s.
* ΔT: reimplement the model **as documented in the Swiss Ephemeris
  manual** (Stephenson-Morrison-Hohenkerk 2016 long-term + tabulated
  IERS values for the instrumented era + SE's tidal-acceleration
  adjustment), from the published description and tables only — no
  code porting.  Acceptance: |ΔT_ours − ΔT_SE| ≤ 0.01 s on the golden
  fixture dates and ≤ 0.05 s across 1800–2399.  Rationale: UT1 feeds
  ARMC at 15.04 "/s, so 0.01 s keeps angles within ±0.15" (display
  precision is 1"); the Moon moves 0.55 "/s, so 0.01 s ⇒ ≤ 0.006".
* `resolve()`/`from_utc()` keep the existing UTC→UT1 convention
  (today's swe_utc_to_jd behavior, e.g. +0.74 s on 1994-07-29 —
  verified against astro.com's hosted swetest during v1 UAT).
* Obliquity/nutation: IAU 2006/2000A via ERFA.  SE's values may differ
  at the milli-arcsecond level (it uses its own precession splice);
  K1 measures the actual gap before acceptance thresholds are locked.

## 6. Derived lunar points & Chiron

* TRUE_NODE: osculating ascending node of the geocentric lunar orbit
  from DE440 state vectors (standard osculating-elements formulas).
  Parity target vs SE ≤ 0.01".
* MEAN_NODE / MEAN_APOGEE (Lilith): mean lunar elements polynomials
  (Chapront ELP-2000/82 series as published in Meeus, *Astronomical
  Algorithms*, ch. 47 / Chapront-Touzé & Chapront 1988).  SE uses a
  Moshier fit of the same theory; parity target ≤ 0.5" (≪ 1" display).
  If K2 measures worse, document the delta — do not port SE constants
  beyond what the published papers give.
* CHIRON: Horizons-generated SPK, same reduction pipeline.  Parity
  target vs SE ≤ 0.05" (independent orbit solutions differ slightly).
* SOUTH_NODE_*: derived (+180°) as today, outside the kernel.

## 7. Houses & angles (clean-room)

Inputs: ARMC = `erfa.gst06a(UT1, TT)` + east longitude; true obliquity
ε; geographic latitude φ.  Sources: published house mathematics
(Holden, *House Division*; Munkasey's formulary; standard spherical
trigonometry) — **the SE source tree stays closed during this work**.

* Closed-form: ASC, MC, DSC, IC, Vertex, Equal, Whole-sign, Porphyry,
  Regiomontanus, Campanus.
* Koch: oblique-ascension semi-arc division.
* Alcabitius: diurnal/nocturnal semi-arc hour division.
* Placidus: fixed-point iteration on the semi-arc proportion (seed =
  Porphyry cusp, ~6–8 iterations); beyond the polar circles the
  iteration has no solution → raise, caught by the existing
  `polar_fallback` logic (whose semantics do not change).
* Acceptance: vs swetest ≤ 0.001" for every system over the §9 grid ×
  latitudes {0°, ±31.911°, ±48.4°, ±59.93°, ±66.99°}; polar fixtures
  reproduce today's flags byte-for-byte.

## 8. Sidereal, fixed stars, rise/set

* Ayanamsas (lahiri, krishnamurti, raman, fagan-bradley): accumulated
  precession from each mode's published defining constants (t0,
  ayan_t0 — documented in the SE manual; constants are facts, not
  code).  Same nutation treatment as SE's native sidereal mode — the
  "tropical minus get_ayanamsa" ≈14" nutation trap documented in
  TECHNIQUES.md stays forbidden.  Acceptance: vs `swetest -sid…`
  ≤ 0.01" per mode.
* Fixed stars: Hipparcos positions + proper motion (`erfa.pmsafe`) →
  of-date via the §4 matrix.  Parity vs `sefstars.txt` ≤ 0.5"
  (both derive from Hipparcos; conjunction orb is 1°, display 1").
* Rise/set (planetary hours): standard altitude −0.8333° (refraction +
  solar semi-diameter, disc center convention as used today), root on
  altitude function.  Acceptance: fixture sunrise/sunset within ±1 s.

## 9. Verification & acceptance gate (K7)

* Grid: the existing 65-instant seeded grid, 1800–2399, 4 locations ×
  2 house systems (verify/report.py), extended with the §7 latitude set.
* Three-way: ours-vs-swetest AND ours-vs-Skyfield — planets lon/lat
  ≤ 0.01", speeds ≤ 1e-6 °/day, houses/angles ≤ 0.001" (swetest only),
  sidereal ≤ 0.01".
* Golden snapshots regenerated under the new backend with a mandatory
  diff report: expectation ≥95% byte-identical; every changed byte is
  a last-arcsecond ±1 flip explained by DE431→DE440 or the ΔT model,
  itemized in CHANGELOG.  Format v1 headers unchanged.
* All 323 tests green; property tests untouched (kernel-agnostic).
* Performance: full dossier (`--format both`) ≤ 5 s (see §10).
* verify_report.md gains a backend column (de440 | swiss).

## 10. Performance budget

Root-finding (returns, transit exact-times, VOC) dominates call count
(10³–10⁴ evals/dossier).  Mitigations: one `pnm06a` matrix per instant
shared across bodies; jplephem/pyerfa are numpy-vectorized — sample
search windows on coarse JD arrays in one shot, then refine locally;
memoize SPK segment lookups.  Budget: ≤ 50 µs per body-instant
amortized ⇒ dossier well under the 5 s ceiling (today ~2 s with SE).

## 11. Licensing & clean-room protocol

* New runtime deps: MIT/BSD only; data public domain / free-use.
* `vendor.sh` splits: default profile fetches kernel data only; a
  `--with-swiss` dev profile builds pyswisseph + swetest for the
  verification harness and the optional `backend="swiss"` (clearly
  marked AGPL, never in wheels/releases).
* Repo relicenses to Apache-2.0 at K8, after CI proves the default
  distribution contains no SE code or data; NOTICE rewritten; the
  "Swiss Ephemeris" name is used only factually (verification
  reference), never in branding.
* Clean-room: implementation works from published papers, the SE
  *manual* (a published description), IERS/JPL/ESA data, and black-box
  swetest outputs.  Nobody opens `swehouse.c`/`swephlib.c` while
  writing the corresponding module.

## 12. Milestones (K-series; each slice = verified + pushed)

* **K0 probe** — throwaway venv: jplephem + pyerfa + de440 excerpt;
  Sun/Moon/Mars apparent lon vs swetest over ~20 instants; measure
  error and µs/call.  Exit: ≤ 0.01" demonstrated, perf plausible.
* **K1 time & frames** — UTC/TT/UT1, ΔT model, obliquity/nutation,
  ecliptic-of-date transform; ΔT parity table vs SE.
* **K2 planetary pipeline** — 10 planets + Sun/Moon: lon/lat/dist/
  speed/RA/dec; grid-verified.
* **K3 derived points** — true/mean node, Lilith, Chiron SPK.
* **K4 houses** — 8 systems + angles + polar semantics.
* **K5 sidereal** — 4 ayanamsas; vedic snapshot parity.
* **K6 stars & hours** — Hipparcos stars, rise/set.
* **K7 switchover** — `backend` flag, default de440, three-way verify,
  snapshot diff report, perf gate, engine 2.0.0-rc.
* **K8 license flip** — vendor split, Apache-2.0, NOTICE/README/
  CHANGELOG, release 2.0.0.

## 13. Risks

| risk | mitigation |
|---|---|
| ΔT parity pre-1900 fixtures | SE manual tables; if 0.01 s unreachable, accept ±1" snapshot flips, itemized |
| Placidus polar exactness | fixture-driven (polar/high-lat-ok already exist); fallback logic is ours and unchanged |
| mean node/Lilith constants differ from SE's fit | 0.5" tolerance ≪ display; document |
| Chiron orbit-solution drift vs SE | 0.05" target; both well under display |
| de440 excerpt integrity | pinned SHA-256 + span assertion in fetch script |
| pure-python overhead in search loops | vectorized grids + shared PN matrix; K0 measures before commitment |
| Skyfield unavailable in restricted envs | it is dev-only; runtime needs jplephem+pyerfa only |
