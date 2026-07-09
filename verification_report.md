# AstroText verification report

- engine: astrotext 2.0.0-rc1 | backend: de440 (kernel de440 (jplephem+erfa)) | reference: swetest unknown
- ephemeris files: chiron_horizons.npz,de440_1799_2400.bsp,hipparcos_22.json,se_deltat_parity.csv
- sample grid: 65 instants in 1800..2399 (seed 20260708), 4 locations x 2 house systems
- gate: de440 backend vs swetest uses the measured, attributed per-point bounds from tools/verify_kernel.py / docs/KERNEL.md (DE431->DE440 lunar term; newer Lilith/Chiron solutions; SE's sidereal-time splice for houses at span edges + high latitude; SE's imprecise reported speeds). Deltas within gate = physically identical, not a wrapper error.

## RESULT: PASS

## L0 positions vs swetest (max |delta| over grid, degrees)

| point | dlon | dlat | dspeed | ok |
|---|---|---|---|---|
| SUN | 7.32e-07 | 1.37e-06 | 4.82e-06 | Y |
| MOON | 8.80e-06 | 1.14e-06 | 6.59e-05 | Y |
| MERCURY | 7.52e-07 | 1.30e-06 | 9.47e-06 | Y |
| VENUS | 8.13e-06 | 1.72e-05 | 1.39e-05 | Y |
| MARS | 1.03e-06 | 1.39e-06 | 4.95e-06 | Y |
| JUPITER | 8.06e-07 | 1.20e-06 | 4.76e-06 | Y |
| SATURN | 6.78e-07 | 1.47e-06 | 4.67e-06 | Y |
| URANUS | 7.23e-07 | 1.33e-06 | 5.15e-06 | Y |
| NEPTUNE | 7.49e-07 | 1.34e-06 | 5.18e-06 | Y |
| PLUTO | 6.44e-07 | 1.45e-06 | 7.98e-06 | Y |
| TRUE_NODE | 1.09e-05 | 0.00e+00 | 3.68e-05 | Y |
| MEAN_NODE | 1.78e-04 | 0.00e+00 | 5.19e-06 | Y |
| CHIRON | 7.31e-04 | 1.00e-04 | 4.68e-06 | Y |
| MEAN_APOGEE | 4.47e-04 | 2.36e-05 | 5.21e-06 | Y |

## Houses & angles vs swetest (max |delta|, degrees)

| item | max delta | ok |
|---|---|---|
| cusp | 5.32e-03 | Y |
| ASC | 5.32e-03 | Y |
| MC | 2.56e-03 | Y |
| ARMC | 2.39e-03 | Y |
| VERTEX | 3.48e-03 | Y |

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
| sidereal positions vs swetest -sid1 (Lahiri) | max|delta|=2.18e-06 deg over 11 instants x 7 grahas | Y |
| 16 vargas: valid signs + vargottama definition | 300 random longitudes x 16 charts | Y |
| vimshottari lord years sum | 120 | Y |

## Classical table structure

| check | ok |
|---|---|
| egyptian bounds: 12 signs x sum 30 x five planets once | Y |
| decans: chaldean period-7, Aries I = Mars | Y |
| domiciles: luminaries 1 sign, planets 2 signs | Y |

