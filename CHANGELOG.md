# Changelog

All notable behavior changes to the engine and its output formats.
Engine follows semver; the text/JSON format carries its own version
(`v1` in line 1 of every text file; `format_version` in the JSON envelope).

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
