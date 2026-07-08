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

## Vedic layer (M5)

* **Sidereal core**: Swiss Ephemeris NATIVE sidereal mode (`FLG_SIDEREAL`
  after `set_sid_mode`).  A manual "tropical minus get_ayanamsa_ut" is
  forbidden: it differs by ~nutation (measured 3-14 arcsec).  Ayanamsa
  knob: Lahiri (default) / Krishnamurti / Raman / Fagan-Bradley.
  Cross-verified bit-level against `swetest -sid1`.
* **Grahas**: Sun..Saturn + Rahu/Ketu.  Nodes default MEAN (traditional
  mainstream; 'true' knob); Ketu = Rahu + 180.  Whole-sign bhavas from the
  sidereal Lagna.
* **Nakshatras**: 27 x 13deg20', Ashwini at 0 sidereal Aries; 4 padas;
  Vimshottari lords (Ketu Venus Sun Moon Mars Rahu Jupiter Saturn Mercury).
* **Panchanga**: tithi (12 deg), karana (Kimstughna + 7 movable x 8 +
  Shakuni/Chatushpada/Naga), yoga (sum/13deg20', 27 names), vara.  Sidereal
  longitudes (tithi/karana are ayanamsa-invariant; yoga is not).
* **Shodashavarga**: all 16 divisional charts per BPHS (rules and
  commonly-confused start-sign tables documented in vargas.py; D2 =
  Parashara hora, only Leo/Cancer).  Vargottama = same sign in D1 and D9.
* **Chara karakas**: 8-scheme (with Rahu reversed: 30 - deg); AK AmK BK MK
  PiK PuK GK DK by descending advancement; 7-scheme knob; ties flagged.
* **Graha drishti**: whole-sign; 7th for all, Mars 4/8, Jupiter 5/9,
  Saturn 3/10; nodes cast none by default (tradition varies — knob later).
* **Vimshottari**: 120y; lord years Ketu7 Venus20 Sun6 Moon10 Mars7 Rahu18
  Jupiter16 Saturn19 Mercury17; first lord = Moon's nakshatra lord, balance
  = unelapsed fraction x years; sub-periods proportional starting from the
  parent's lord; 3 levels rendered (819 periods); year = 365.25d (knob).
  Deeper levels (sookshma+) and other dashas (Yogini, Chara): backlog.
* Backlog: shadbala, ashtakavarga, yogas catalog, bhava chalit (Sripati),
  KP sub-lords, muhurta tools.
* Adversarially reviewed (independent BPHS re-derivation, incl. 7
  hand-executed varga test cases and value-by-value start-sign tables):
  zero mismatches.  Tradition-variant notes: dasha year length (365.25
  default vs 360 savana), node drishti (none by default), MK/PiK order in
  some karaka recensions, cyclical-hora / Somnath-drekkana alternatives —
  all exposed as knobs or documented defaults.
