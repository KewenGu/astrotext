# AstroText API

Three facades — **Python library**, **CLI**, **MCP server** — over one
five-layer pure-function pipeline.  Everything is a frozen dataclass;
identical inputs yield byte-identical outputs at every layer.

```
input resolution -> Moment -> Chart -> technique reports -> rendered views
   (gazetteer)      (L0)      (L1)         (L2)           (L4 text/json)
                                                 facades: lib / CLI / MCP (L5)
```

Design rules that hold everywhere:

1. **Pure functions over immutable data.** A Chart is a function of
   (Moment, Settings); every technique is a function of Charts; renderers
   are views.  Nothing mutates, nothing reads clocks or randomness.
2. **No hidden defaults.** Every number-changing choice is a Settings
   field, echoed into output headers by `describe()`.
3. **Fail loudly.** Nonexistent local times, missing ephemeris files,
   sect-dependent techniques on unknown birth times: exceptions, not
   guesses.  Ambiguity that CAN be resolved produces warning flags that
   flow into rendered headers.
4. **Two views, one source.** Text (LLM-facing) and JSON (code-facing)
   render from the same objects; tests pin their agreement.

---

## L0 — time & space  (`astrotext.timespace`)

```python
Place(lat, lon, name=None, tz=None, elevation_m=0.0)   # frozen

resolve(local: datetime,            # NAIVE civil time
        place: Place,
        tz: str | None = None,      # overrides place.tz: IANA | "LMT" | "UTC+HH:MM"
        calendar: str = "gregorian",  # or "julian" (pre-reform dates)
        fold: int = 0,              # ambiguous (fall-back) hour: 0 first, 1 second
        ) -> Moment
from_utc(aware_dt, place) -> Moment  # e.g. transit "now"

Moment: local, place, calendar, tz_used, utc_offset, utc,
        jd_ut, jd_tt, delta_t_sec, flags: tuple[str, ...]
```

Raises `NonexistentLocalTime` (DST gap) and `TimezoneResolutionError`.
Warnings (`ambiguous-local-time:...`, `lmt-used:...`, `tzdb-lmt-era:...`)
travel inside `Moment.flags` and surface in every rendered header.

### Gazetteer  (`astrotext.timespace.gazetteer`)

```python
lookup(query, country=None, limit=5) -> list[GazetteerHit]
resolve_place(query, country=None) -> (Place, flags)   # raises PlaceNotFound
```

170k GeoNames places; staged matching (exact name/ascii -> alternates,
with country-filter fallthrough), curated zh-exonym supplement checked
first (纽约/罗马/河内...), population ranking, ambiguity flags.

## L0 — ephemeris  (`astrotext.ephem`)

```python
eph = Ephemeris(ephe_path=None, strict_files=True)   # or default_ephemeris()
eph.state(jd_ut, "SUN", extra_flags=0, sidereal=False) -> BodyState
eph.houses(jd_ut, lat, lon, hsys="P", sidereal=False) -> (cusps, angles)
eph.configure_sidereal("lahiri"); eph.ayanamsa(jd_ut)
```

`BodyState`: lon/lat/dist + speeds + RA/dec + retrograde.  Missing data
files raise `EphemerisDataMissing` rather than silently degrading to the
Moshier model.  Point keys are the stable registry names
(`SUN..PLUTO, TRUE_NODE, MEAN_NODE, CHIRON, MEAN_APOGEE`, derived
`SOUTH_NODE_*`) from `astrotext.ephem.points`.

## L1 — the chart  (`astrotext.core`)

```python
Settings(zodiac="tropical", house_system="P", polar_fallback="O",
         points=(...), aspects=(...), angle_points=("ASC","MC"),
         node="true", unknown_time=False, ...)        # frozen
MODERN, HELLENISTIC                                   # presets
settings.with_(house_system="W")                      # immutable update
settings.describe() -> list[str]                      # header echo

compute_chart(moment, settings=None, eph=None, kind="natal") -> Chart
```

`Chart` aggregates: `points` (ChartPoint: lon/speed/dec/OOB/sign/house),
`cusps`, `angles`, `aspects` (AspectHit with signed orb + A/S/E phase),
`dignities`, `receptions`, `dispositors`, `lots`, `moon` phase, `antiscia`,
sect (`is_day`, `sun_altitude`), `flags`.  Unknown birth time suppresses
houses/angles/lots and flags the Moon's daily drift.

## L2 — techniques  (`astrotext.techniques`)

All pure functions of charts/moments; each returns its own report object.

```python
compute_transits(natal, now, orb=3.0, window_days=400) -> TransitReport
    # relocated sky chart, natal-wheel placement, tight-orb hits with ALL
    # exact timestamps in a per-body window, Moon void-of-course
compute_progressed(natal, target, kind="secondary"|"tertiary"|"minor",
                   year="tropical", month="tropical") -> ProgressedReport
compute_solar_arc(natal, target) -> SolarArcReport
compute_return(natal, target, body="SUN", place=None,
               precessed=False) -> ReturnReport      # any-planet returns
firdaria(natal, cycles=2, nodes="after-mars") -> list[FirdariaPeriod]
profections(natal, target) -> ProfectionsReport      # solar-return year bounds
```

Vedic (`astrotext.techniques.vedic`):

```python
VedicSettings(ayanamsa="lahiri", node="mean", karaka_scheme=8,
              dasha_year_days=365.25, vargas=(1,2,...,60))
compute_vedic_chart(moment, settings=None, unknown_time=False) -> VedicChart
varga_sign(sid_lon, d) / varga_table(lons, vargas) / vargottama(lon)
vimshottari(moon_sid_lon, birth_jd, year_days=365.25, max_level=3)
nakshatra_of(sid_lon) -> Nakshatra
```

Shared machinery: `techniques.search.angular_roots(lon_of, target, t0, t1,
step)` — wrap-safe root finder (returns/exact hits/VOC all use it).

## L4 — renderers  (`astrotext.render`)

Text (LLM-facing; grammar in FORMAT.md; `parse()` proves losslessness):

```python
render_chart(chart, subject=None, hour=None, stars=None, extra_meta=())
render_transits / render_progressed / render_solar_arc / render_return
render_firdaria / render_profections
render_vedic_rashi / render_vargas / render_vimshottari
parse(text) -> dict          # round-trip checker
render_glossary()            # EN->ZH terminology
```

JSON (code-facing; full float precision, sort_keys, deterministic):

```python
from astrotext.render import json_out as J
J.to_json(J.chart_to_dict(chart, ...))       # + transits_to_dict, ... ,
                                             #   vimshottari_to_dict
```

## L5 — facades

### Library facade  (`astrotext.dossier`)

```python
Subject(name, local, place, tz=None, calendar="gregorian",
        fold=0, unknown_time=False, notes=())
build_dossier(subject, now_utc, current_place,
              settings=MODERN, fmt="both") -> dict[str, str]   # pure
generate_dossier(..., out_dir) -> Path                         # writes
```

15 text files (+13 JSON siblings): index, meta+glossary, natal x2,
transits, progressions x3, returns x2, firdaria, profections, vedic x3.

### CLI

```bash
python -m astrotext dossier --name X --birth "1988-06-15 14:30" \
    --birth-place 北京 --now "2026-07-08 12:00" --cur-place 纽约 \
    [--lat/--lon/--tz ...] [--format text|json|both] [--unknown-time]
python -m astrotext verify     # regenerate verification_report.md
python -m astrotext mcp        # stdio MCP server
```

### MCP server  (`python -m astrotext mcp`)

Zero-dependency stdio JSON-RPC (MCP 2024-11-05).  Tools:

| tool | purpose |
|---|---|
| `astro_resolve_place` | place name (zh OK) -> ranked lat/lon/tz candidates |
| `astro_chart` | one of 13 chart kinds as text (or JSON view) |
| `astro_dossier` | index + meta + selected chart files in one call |

Chart kinds: `natal, natal_hellenistic, transits, secondary, tertiary,
solar_arc, solar_return, lunar_return, firdaria, profections,
vedic_rashi, vedic_vargas, vedic_vimshottari`.  Subjects are passed
per-call (stateless); an LRU on the computed dossier makes repeated pulls
for one subject instant.  MCP output is byte-identical to CLI files
(pinned by tests).

---

## Stability contract

* Stable identifiers: point keys, chart kinds, dossier file stems, text
  format `v0` (line 1 of every file), JSON envelope
  `{"format":"astrotext-json","format_version":0}`.
* Breaking changes to any of these bump the format version; the engine
  emits exactly one format version per release.
* Warnings are data: readers (human or agent) must surface `warning=`
  lines; a text file not ending in `== END ==` is truncated and invalid.
