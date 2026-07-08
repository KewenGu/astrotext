# AstroText plain-text format — v0 (normative)

The text IS the database.  Design goals, in priority order: (1) zero
arithmetic left to the reader, (2) deterministic byte-for-byte output,
(3) token economy, (4) human-checkable.

## Line grammar

```
line 1     == ASTROTEXT <KIND> v0 ==       KIND: NATAL | TRANSITS | ...
meta       key=value                        until the first section header
section    -- NAME --
row        field | field | ...              first field is the row key
comment    # ...                            column legends; ignorable
empty row  (none)                           a section with no rows
last line  == END ==                        guards against truncation
```

Values never contain `|`.  A file that does not end in `== END ==` is
truncated and MUST be discarded by the reader.

## Meta zone

`subject`, `local` (+ `calendar=gregorian|julian`), `place`, `tz`, `utc`,
`offset`, `jd-ut` (8 dp), `delta-t`, one `set:`-prefixed line per settings
group, `houses-used`, `sect` (+`sun-altitude`), `obliquity`, and one
`warning=` line per flag (or `warning=(none)`).  Warnings are part of the
data: an interpreting agent must surface them (e.g. ambiguous birth times).

## Numbers & conventions

* Zodiacal position: `24Gem19'59"` — degrees(2) sign-abbr minutes(2)
  seconds(2), rounded to 1"; sign abbreviations `Ari Tau Gem Can Leo Vir Lib
  Sco Sag Cap Aqu Pis`.
* `lon` decimal degrees, 6 dp, [0, 360).  `lat`/`decl` signed.  `speed` in
  deg/day, signed; negative = retrograde.
* Aspect orb: SIGNED `separation - exact_angle` in degrees, 3 dp.
* Phases: `A` applying, `S` separating, `E` exact (<1'), `-` not defined
  (angles have no speed).
* Tags column: `R` retrograde, `OOB` out-of-bounds declination, `-` none.

## Sections (NATAL)

`POINTS`, `ANGLES`, `HOUSES (<letter>)`, `ASPECTS`,
`DIGNITIES (classical seven, day|night chart)`, `RECEPTIONS (mutual)`,
`DISPOSITORS (domicile chains)`, `LOTS`, `MOON`, `ANTISCIA (orb x)`,
`FIXED STARS (conjunctions, orb x)`, `PLANETARY HOUR`.

Sections appear in that order.  Suppressed content (unknown birth time:
ANGLES/HOUSES/LOTS/PLANETARY HOUR) disappears entirely rather than rendering
empty — plus an explanatory `warning=`.

### DIGNITIES row

`PLANET | essentials-or-peregrine | score | sign-ruler/exalted/(trip day,night,part)/bound/decan`

The rulers part describes the planet's *position* (who has dignity there),
so an agent can derive receptions and lordships without tables.

### DISPOSITORS row

`PLANET | A > B (final)` — final = self-ruling terminus; `(loop)` = closed
cycle without a final dispositor.

## The JSON view (v0)

Every dossier data file has a `.json` sibling (`--format both`, the
default; `text` / `json` narrow it).  Division of labor, measured on a
real dossier (10 data files):

| view | bytes | ~tokens | role |
|---|---|---|---|
| text v0 | 40.0 KB | ~11.1k | LLM-context reading: token-lean, astrologese-native, human-checkable |
| json v0 | 99.4 KB (2.48x) | ~27.6k | pipelines/code: standard tooling, schema-checkable, FULL float precision |

Rules: both views render from the same computed objects (neither is parsed
from the other); JSON is `sort_keys` + compact separators + exact doubles,
so it is byte-deterministic too; envelope keys `format: astrotext-json`,
`format_version: 0`.  Feed TEXT to language models; hand JSON to code.
If JSON must enter an LLM context, prefer extracting the needed section,
not the whole file.

## Versioning

Breaking changes bump `v0` -> `v1` in line 1; readers must check it.
The engine writes exactly one format version per release.
