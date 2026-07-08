# AstroText verification report

- engine: astrotext 1.0.0 | Swiss Ephemeris 2.10.03 (pyswisseph, built from source) | swetest unknown
- ephemeris files: seas_12.se1,seas_18.se1,semo_12.se1,semo_18.se1,sepl_12.se1,sepl_18.se1
- sample grid: 65 instants in 1800..2399 (seed 20260708), 4 locations x 2 house systems
- tolerances: lon/lat/speed/cusp <= 2e-07 deg (0.00072 arcsec)

## RESULT: PASS

## L0 positions vs swetest (max |delta| over grid, degrees)

| point | dlon | dlat | dspeed | ok |
|---|---|---|---|---|
| SUN | 4.84e-08 | 4.90e-08 | 5.00e-08 | Y |
| MOON | 4.99e-08 | 4.98e-08 | 4.87e-08 | Y |
| MERCURY | 4.95e-08 | 4.88e-08 | 4.89e-08 | Y |
| VENUS | 4.97e-08 | 4.97e-08 | 4.98e-08 | Y |
| MARS | 4.97e-08 | 4.95e-08 | 4.98e-08 | Y |
| JUPITER | 4.95e-08 | 4.94e-08 | 4.94e-08 | Y |
| SATURN | 4.94e-08 | 4.96e-08 | 4.98e-08 | Y |
| URANUS | 4.77e-08 | 4.94e-08 | 4.99e-08 | Y |
| NEPTUNE | 4.72e-08 | 4.91e-08 | 4.90e-08 | Y |
| PLUTO | 4.98e-08 | 4.76e-08 | 5.00e-08 | Y |
| TRUE_NODE | 4.76e-08 | 0.00e+00 | 4.94e-08 | Y |
| MEAN_NODE | 4.95e-08 | 0.00e+00 | 4.95e-08 | Y |
| CHIRON | 4.90e-08 | 4.98e-08 | 4.99e-08 | Y |
| MEAN_APOGEE | 4.96e-08 | 4.93e-08 | 4.97e-08 | Y |

## Houses & angles vs swetest (max |delta|, degrees)

| item | max delta | ok |
|---|---|---|
| cusp | 4.99e-08 | Y |
| ASC | 4.91e-08 | Y |
| MC | 4.93e-08 | Y |
| ARMC | 4.84e-08 | Y |
| VERTEX | 4.98e-08 | Y |

## Time & timezone acceptance cases

| case | got | expected | ok |
|---|---|---|---|
| 1988-06-15 14:30 Beijing (summer, DST era) | 1988-06-15 05:30 UTC | 1988-06-15 05:30 UTC | Y |
| 1988-01-15 14:30 Beijing (winter, DST era) | 1988-01-15 06:30 UTC | 1988-01-15 06:30 UTC | Y |
| 1986-05-04 02:30 Beijing (DST gap) | NonexistentLocalTime | NonexistentLocalTime | Y |
| 1986-09-14 01:30 Beijing (ambiguous, fold=0) | 16:30 +flag | 16:30 +flag | Y |
| 1986-09-14 01:30 Beijing (ambiguous, fold=1) | 17:30 | 17:30 | Y |
| 1900-06-01 12:00 Beijing (tzdb LMT era +08:05:43) | 03:54:17 +flag | 03:54:17 +flag | Y |
| 1850-03-10 12:00 Beijing LMT (lon 116.4074 -> +07:45:38) | 04:14:22 | 04:14:22 | Y |
| 2000-01-01 12:00 UTC -> JD/deltaT sanity | jd_ut=2451545.00000411 dT=63.83s | jd~2451545.0 dT~63.8s | Y |
| 1500-02-20 12:00 julian calendar, LMT lon 0 | jd_ut=2268983.000000 | jd_ut=2268983.000000 | Y |

## M1 chart layer: golden fixtures (snapshot + round-trip)

| fixture | status | ok |
|---|---|---|
| einstein | snapshot== roundtrip=ok | Y |
| jobs | snapshot== roundtrip=ok | Y |
| monroe | snapshot== roundtrip=ok | Y |
| obama | snapshot== roundtrip=ok | Y |
| freud | snapshot== roundtrip=ok | Y |
| curie | snapshot== roundtrip=ok | Y |
| hepburn | snapshot== roundtrip=ok | Y |
| bruce-lee | snapshot== roundtrip=ok | Y |
| beijing-dst | snapshot== roundtrip=ok | Y |
| beijing-dst-ambiguous | snapshot== roundtrip=ok | Y |
| polar | snapshot== roundtrip=ok | Y |
| equator | snapshot== roundtrip=ok | Y |
| sydney | snapshot== roundtrip=ok | Y |
| midnight | snapshot== roundtrip=ok | Y |
| lmt-1850 | snapshot== roundtrip=ok | Y |
| julian-cal | snapshot== roundtrip=ok | Y |
| unknown-time | snapshot== roundtrip=ok | Y |
| hellenistic | snapshot== roundtrip=ok | Y |
| high-lat-ok | snapshot== roundtrip=ok | Y |
| retro-heavy | snapshot== roundtrip=ok | Y |

## M2 timed layer: transits / progressions / solar arc

| fixture | status | ok |
|---|---|---|
| einstein | snapshots== arc==dSun & age0==natal: ok | Y |
| beijing-dst | snapshots== arc==dSun & age0==natal: ok | Y |

## M5 vedic layer

| check | detail | ok |
|---|---|---|
| sidereal positions vs swetest -sid1 (Lahiri) | max|delta|=4.89e-08 deg over 11 instants x 7 grahas | Y |
| 16 vargas: valid signs + vargottama definition | 300 random longitudes x 16 charts | Y |
| vimshottari lord years sum | 120 | Y |

## Classical table structure

| check | ok |
|---|---|
| egyptian bounds: 12 signs x sum 30 x five planets once | Y |
| decans: chaldean period-7, Aries I = Mars | Y |
| domiciles: luminaries 1 sign, planets 2 signs | Y |

