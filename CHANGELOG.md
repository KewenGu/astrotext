# Changelog

All notable behavior changes to the engine and its output formats.
Engine follows semver; the text/JSON format carries its own version
(`v1` in line 1 of every text file; `format_version` in the JSON envelope).

## 2.0.0 — unreleased (K8 license flip)

- **Relicensed AGPL-3.0 → Apache-2.0** (LICENSE + NOTICE rewritten). The
  default distribution is permissively licensed end to end and free to
  embed, host and commercialize. Runtime stack: numpy, jplephem (MIT),
  pyerfa/ERFA (BSD-3), DE440 (public domain), Hipparcos (free-use).
- **Swiss Ephemeris fully removed from the default distribution.** It
  remains an *optional* `backend="swiss"` reference for cross-checks,
  built only by `make vendor-swiss` (AGPL, dev/verify, never in wheels).
  The `.se1` data and `sefstars.txt` are untracked and gitignored; no SE
  code or data is committed or shipped.
- **`vendor.sh` split into two profiles:** default (kernel deps + DE440
  excerpt + pytest, no Swiss) and `--with-swiss` (adds pyswisseph +
  swetest + `.se1`). New `make` targets: `vendor-swiss`, `check-license`.
- **New gate `tools/check_no_swiss.py`** (`make check-license`): proves
  the shipped tree carries no `.se1` / `sefstars.txt` / SE C sources and
  that the de440 backend computes with `swisseph` unimportable. Release
  of 2.0.0 is gated on this passing plus `make verify` on the swiss
  profile.
- `./astrotext` launcher no longer requires the compiled `swisseph`
  module; it checks the de440 kernel deps (jplephem, erfa) and the DE440
  excerpt instead. pyproject declares `license = "Apache-2.0"`.

## 2.0.0-rc1 — 2026-07-08 (K7 switchover)

- **Default computation backend flips to `de440`** (KERNEL.md, K0–K6):
  the in-repo DE440-excerpt + ERFA kernel with our own houses, sidereal,
  fixed-star and rise/set implementations. Swiss Ephemeris becomes an
  optional `backend="swiss"` reference (dev/verify profile only, AGPL,
  excluded from wheels). Select via `Ephemeris(backend=...)` or
  `$ASTROTEXT_BACKEND`. New runtime deps: numpy, jplephem (MIT), pyerfa
  (BSD-3); no Swiss code or data in the default distribution.
- **Format v1 unchanged.** Line-1 version labels, sections, columns and
  number formats are identical; the round-trip parser is untouched.
- **Golden snapshots regenerated under de440.** Mandatory diff report
  (20 natal + timed + vedic fixtures): **99.451% byte-identical**
  (633 of 115 375 bytes differ), well past the ≥95% gate. Every changed
  byte is attributed:
  - Arcsecond **display (DMS) columns are byte-identical** except **7**
    single ±1″ flips, all on the two points K3 documents as
    orbit-solution/fit differences vs SE: **MEAN_APOGEE** (mean-node
    ELP-2000 fit vs SE's Moshier, ≤1.6″) and **CHIRON** (newer JPL
    Horizons solution vs SE's older one, ≤1″). Both under the 1″ display
    convention.
  - The raw 6-decimal fields carry last-digit noise: max drift lon
    2.3e-4° (Chiron/Lilith), lat 5.8e-5°, lon-speed 6.8e-5°/day (the
    K2-documented DE431→DE440 lunar term). Timed layers show the same
    pattern plus sub-arcsecond root-finder residual shifts
    (e.g. return-JD ≤5e-7 d ≈ 40 µs).
- **Fix:** `kernel/bodies.py` `frame="j2000"` path unpacked `erfa.bp06`
  as 2 values; ERFA returns 3 (rb, rp, rbp). Corrected — this path feeds
  precession-corrected returns.
- Full de440 test suite green (1329 collected; kernel 1043, properties
  166, edge 22, golden 62, smoke 3; cross/swetest skip cleanly off the
  swiss profile). Property tests untouched (kernel-agnostic).
- **Remaining for release (2.0.0):** the swetest/Skyfield three-way
  reference gate (`make verify`) runs on the dev/swiss profile (K8),
  plus the vendor split and Apache-2.0 relicense.

## 1.0.0 — 2026-07-08

- **Text format frozen at v1** (was draft v0). The only change from v0 is
  the version label in line 1 of every file and in the dossier meta/index
  headers — structure, sections, number formats and conventions are
  unchanged and now under the compatibility contract in docs/FORMAT.md.
- **JSON envelope** `format_version` 0 -> 1 (same data, same keys).
- HTTP route prefix stays `/v0/` — it versions the REST contract, which is
  independent of the text format version.
- Round-trip parser accepts any `v<N>` header (strict on structure).
- Golden snapshots (20 natal + timed + vedic) regenerated for v1; full
  suite green (323 tests); `make verify` PASS (swetest agreement <= 5e-8 deg).
- Freeze gated on UAT cross-checks (2026-07-08, sample chart 1994-07-29
  10:30 Jiangyin):
  - astro.com hosted swetest 2.10.03: tropical planets, 12 Placidus cusps,
    ASC/MC/ARMC/Vertex all <= 0.1" once fed our exact jd_ut (confirming the
    deliberate UTC->UT1 (+0.74s) convention via swe_utc_to_jd).
  - drikpanchang.com: tithi/karana/yoga/nakshatra-pada boundaries to the
    minute; sidereal Sun/Moon signs match.
  - vedicastrochart.com: 9 grahas <= 0.4" (Sun 0.03"), nakshatra-pada 9/9,
    whole-sign bhavas 9/9, D9 10/10, all 9 vimshottari mahadasha bounds
    <= 1 day (their 365.256d year vs our 365.25d knob).
  - astro-seek: user-verified agreement (sidereal).
