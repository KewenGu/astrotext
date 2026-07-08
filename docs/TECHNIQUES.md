# Techniques — definitions, variants, sources

Rule: every technique states its exact convention and the main alternatives.
No hidden defaults (design axiom).  [M2+] marks not-yet-implemented layers.

## L0 conventions

* Positions: apparent geocentric, ecliptic of date, with light-time and
  aberration — Swiss Ephemeris defaults (`FLG_SWIEPH|FLG_SPEED`), identical
  to astro.com.  Sidereal arrives as a flag with the Vedic layer [M5].
* Time: local civil -> UTC (IANA tzdb; DST gap = hard error, ambiguity =
  fold choice + warning) -> JD(UT1) + JD(TT) via `swe_utc_to_jd` (leap
  seconds + SE delta-T model).  LMT mode: 4 min/degree from birth longitude.
* Houses: SE house engine.  Placidus (modern default), Whole-sign
  (hellenistic default), Koch, Porphyry, Regiomontanus, Campanus, Equal,
  Alcabitius available.  Beyond polar circles Placidus/Koch fail ->
  configurable fallback (default Porphyry, matching the astro.com/SE
  substitution) + warning flag.

## Natal chart (M1)

* **Aspects**: angle set + orbs in Settings, echoed in output.  Applying/
  separating from instantaneous relative speed (sign of d|u-θ|/dt);
  `E` within 1'.  Alternative moiety-based orbs: planned as a profile knob.
* **Sect**: day chart iff Sun is on the MC side of the ecliptic ASC-DSC
  axis (Hellenistic convention).  True-altitude cross-check: within ±0.8°
  of the horizon a warning flags sect sensitivity; a disagreement between
  conventions is also flagged.
* **Essential dignities**: domicile (Ptolemy), exaltation with traditional
  degrees, Dorothean triplicities (day/night/participating), Egyptian
  bounds (Valens/Dorotheus; astro.com's default term set), Chaldean decans
  (Aries I = Mars).  Scores: Lilly weights +5/+4/+3/+2/+1, detriment −5,
  fall −4.  Peregrine = no positive essential dignity.  Ptolemaic bounds:
  future knob.
  Variant note (adversarially reviewed): triplicity +3 is granted to the
  sect ruler OR the participating ruler (Dorothean rulers with Lilly-style
  weights).  Strict Lilly uses his own two-ruler triplicities and only the
  sect ruler; strict Dorothean practice varies on the participating ruler.
  Exaltation degrees are stored as metadata; dignity applies sign-wide
  (common practice).
* **Receptions**: mutual receptions by domicile/exaltation (mixed kind when
  asymmetric).
* **Dispositors**: domicile chains over the classical seven; terminus =
  self-ruling planet ("final"), or a loop.
* **Lots**: Fortune = ASC+Moon−Sun (day) / ASC+Sun−Moon (night); Spirit
  mirrored.  (Hermetic lots: backlog.)
* **Moon**: elongation, 8-phase wheel (45° buckets from New), waxing flag,
  illumination (1−cos e)/2.  Void-of-course needs the aspect root-finder ->
  lands with [M3] returns machinery.
* **Antiscia**: solstitial mirror (180−λ), contra-antiscia (360−λ), orb 1°.
* **Fixed stars**: 22 majors, longitude conjunctions ≤1° to points/angles
  (SE `sefstars.txt` positions of date).
* **Planetary hours**: sunrise->sunset 12 + sunset->sunrise 12 unequal
  hours; day = weekday of its sunrise (local); first hour ruler = day
  ruler; Chaldean descending sequence.  Polar no-rise/no-set -> flagged,
  no hour.
* **Out-of-bounds**: |declination| > true obliquity of date.

## [M2] Progressions & directions

* Secondary: 1 civil day after birth = 1 tropical year (per JD).  Angle
  progression method: configurable (solar-arc-on-MC vs progressed-ARMC
  ["Naibod in RA"] vs progressed sidereal time) — default matches astro.com;
  decided and documented in M2.
* Tertiary (Troinski I): 1 day = 1 tropical month.  Variant II documented.
* Solar arc: all points advanced by the secondary Sun's arc.

## [M3] Returns & time-lords

* Returns: solve λ_body(t) = λ_natal exactly (wrap-safe bracketing +
  root-finding to <1s); location = current residence by default (config).
  Precession-corrected variant: knob.
* Firdaria: 75-year cycle; day sequence Sun→Venus→Mercury→Moon→Saturn→
  Jupiter→Mars (+ nodes 3+2), night starts from Moon; sub-periods
  proportional.  Node placement variants documented.
* Profections: annual whole-sign from ASC, 1 sign/year; monthly option;
  year lord = domicile ruler of profected sign.

## [M5] Vedic layer

Sidereal (ayanamsa options, Lahiri default), nakshatras + padas, vargas
(D1/D9/D10 first), Vimshottari dasha from natal Moon nakshatra.
