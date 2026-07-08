"""Time scales for kernel v2 — UTC/TAI/TT/UT1, ΔT, calendars (KERNEL.md §5).

Semantics replicate the engine's v1 conventions bit-for-bit (they were
UAT-verified against astro.com's hosted swetest):

* ``utc_to_jd`` — Swiss Ephemeris ``swe_utc_to_jd`` parity.
  From 1972-01-01 UTC on: TT = UTC + (TAI−UTC from the leap table) + 32.184 s;
  UT1 = TT − ΔT_jpl, solved by a two-step fixed point.
  Before 1972 there is no leap-second UTC: the civil instant is taken as UT1
  directly and TT = UT1 + ΔT_jpl(UT1).  (Measured SE behaviour, 1820–2017:
  |ours − SE| ≤ 1.5e-5 s; see tools/gen_kernel_fixtures.py.)
* ``deltat`` — ΔT in **days** (SE ``swe_deltat`` signature), SWIEPH flavour
  (tidal acceleration of DE431, ndot = −25.80 ″/cy²).
* ``deltat_sec(jd, flavor)`` — seconds; flavours "swieph" and "jpleph".
  They coincide after 1955 (the SE manual's tidal-acceleration adjustment
  applies to epochs before 1955 only).

ΔT is evaluated from ``data/kernel/se_deltat_parity.csv`` — a dense black-box
grid of SE 2.10.03 values (monthly nodes to 2035, quarterly after; linear
interpolation error ≤ 1.7e-4 s by the measured curvature bound; generator:
tools/gen_deltat_parity.py).  The grid — not a reimplementation of the
Stephenson-Morrison-Hohenkerk 2016 splines — is used because the published
spline coefficients (RSPA supplementary) are paywalled/firewalled, while
KERNEL.md §11 sanctions black-box outputs.  Swap-in of a first-principles
model later only has to satisfy the same fixtures.

Leap-second table: USNO ``tai-utc.dat`` (retrieved 2026-07-08), 1972+ steps.
Calendar conversions: Fliegel & Van Flandern (1968) / Meeus, *Astronomical
Algorithms* ch. 7 — proleptic, both calendars, no SE involvement.
"""
from __future__ import annotations

import functools

import numpy as np

from ..config import kernel_data_path

TT_MINUS_TAI = 32.184  # seconds, definition of TT

GREGORIAN = "gregorian"
JULIAN = "julian"

# (jd_utc_of_change, TAI-UTC seconds) — USNO tai-utc.dat, 1972+.
_LEAP_STEPS: tuple[tuple[float, int], ...] = (
    (2441317.5, 10),  # 1972 JAN 1
    (2441499.5, 11),  # 1972 JUL 1
    (2441683.5, 12),  # 1973 JAN 1
    (2442048.5, 13),  # 1974 JAN 1
    (2442413.5, 14),  # 1975 JAN 1
    (2442778.5, 15),  # 1976 JAN 1
    (2443144.5, 16),  # 1977 JAN 1
    (2443509.5, 17),  # 1978 JAN 1
    (2443874.5, 18),  # 1979 JAN 1
    (2444239.5, 19),  # 1980 JAN 1
    (2444786.5, 20),  # 1981 JUL 1
    (2445151.5, 21),  # 1982 JUL 1
    (2445516.5, 22),  # 1983 JUL 1
    (2446247.5, 23),  # 1985 JUL 1
    (2447161.5, 24),  # 1988 JAN 1
    (2447892.5, 25),  # 1990 JAN 1
    (2448257.5, 26),  # 1991 JAN 1
    (2448804.5, 27),  # 1992 JUL 1
    (2449169.5, 28),  # 1993 JUL 1
    (2449534.5, 29),  # 1994 JUL 1
    (2450083.5, 30),  # 1996 JAN 1
    (2450630.5, 31),  # 1997 JUL 1
    (2451179.5, 32),  # 1999 JAN 1
    (2453736.5, 33),  # 2006 JAN 1
    (2454832.5, 34),  # 2009 JAN 1
    (2456109.5, 35),  # 2012 JUL 1
    (2457204.5, 36),  # 2015 JUL 1
    (2457754.5, 37),  # 2017 JAN 1
)
_LEAP_JDS = np.array([j for j, _ in _LEAP_STEPS])
_LEAP_VALS = np.array([v for _, v in _LEAP_STEPS], dtype=float)
_UTC_ERA_START = _LEAP_JDS[0]  # 1972-01-01


class KernelTimeError(ValueError):
    """Raised for instants outside the kernel's supported span."""


@functools.lru_cache(maxsize=1)
def _parity_grid() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    path = kernel_data_path() / "se_deltat_parity.csv"
    try:
        raw = np.loadtxt(path, delimiter=",", comments="#")
    except OSError as exc:
        raise KernelTimeError(
            f"ΔT parity grid missing: {path} — run tools/fetch_kernel_data.py "
            f"or tools/gen_deltat_parity.py"
        ) from exc
    return raw[:, 0], raw[:, 1], raw[:, 2]


def tai_minus_utc(jd_utc: float) -> float:
    """TAI−UTC seconds from the leap table (1972+ only)."""
    if jd_utc < _UTC_ERA_START:
        raise KernelTimeError("no leap-second UTC before 1972-01-01")
    i = int(np.searchsorted(_LEAP_JDS, jd_utc, side="right")) - 1
    return float(_LEAP_VALS[i])


def deltat_sec(jd_ut, flavor: str = "swieph"):
    """ΔT = TT − UT1 in seconds at jd (UT). Vectorized.

    flavor: "swieph" (plain swe_deltat / engine.delta_t parity) or
    "jpleph" (the flavour swe_utc_to_jd applies internally).
    """
    grid_jd, dt_swi, dt_jpl = _parity_grid()
    col = {"swieph": dt_swi, "jpleph": dt_jpl}[flavor]
    j = np.asarray(jd_ut, dtype=float)
    if np.any(j < grid_jd[0]) or np.any(j > grid_jd[-1]):
        raise KernelTimeError(
            f"jd {j!r} outside ΔT parity grid span "
            f"[{grid_jd[0]:.1f}, {grid_jd[-1]:.1f}] (≈1799–2402)")
    out = np.interp(j, grid_jd, col)
    return float(out) if np.isscalar(jd_ut) or j.ndim == 0 else out


def deltat(jd_ut: float) -> float:
    """ΔT in **days** — signature-compatible with swe.deltat."""
    return deltat_sec(jd_ut, "swieph") / 86400.0


def ut1_to_tt(jd_ut1, flavor: str = "swieph"):
    """JD(UT1) → JD(TT)."""
    return jd_ut1 + deltat_sec(jd_ut1, flavor) / 86400.0


def tt_to_ut1(jd_tt, flavor: str = "swieph"):
    """JD(TT) → JD(UT1) by two-step fixed point (ΔT varies slowly)."""
    x = jd_tt - deltat_sec(jd_tt, flavor) / 86400.0
    return jd_tt - deltat_sec(x, flavor) / 86400.0


# --------------------------------------------------------------------------
# calendars — Fliegel & Van Flandern (1968); Meeus, Astr. Algorithms ch. 7
# --------------------------------------------------------------------------

def julday(year: int, month: int, day: int, hour: float = 0.0,
           calendar: str = GREGORIAN) -> float:
    """Civil date → Julian day number (proleptic; swe.julday parity)."""
    y, m = year, month
    if m <= 2:
        y -= 1
        m += 12
    if calendar == GREGORIAN:
        a = y // 100
        b = 2 - a + a // 4
    elif calendar == JULIAN:
        b = 0
    else:
        raise ValueError(f"calendar must be {GREGORIAN!r} or {JULIAN!r}")
    jd = (int(365.25 * (y + 4716)) + int(30.6001 * (m + 1))
          + day + b - 1524.5)
    return jd + hour / 24.0


def revjul(jd: float, calendar: str = GREGORIAN) -> tuple[int, int, int, float]:
    """Julian day → (year, month, day, hour) in the given calendar."""
    z = int(jd + 0.5)
    f = (jd + 0.5) - z
    if calendar == GREGORIAN:
        alpha = int((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    elif calendar == JULIAN:
        a = z
    else:
        raise ValueError(f"calendar must be {GREGORIAN!r} or {JULIAN!r}")
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)
    day = b - d - int(30.6001 * e)
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    return year, month, day, f * 24.0


# --------------------------------------------------------------------------
# UTC → (TT, UT1) — swe_utc_to_jd parity
# --------------------------------------------------------------------------

def utc_to_jd(year: int, month: int, day: int, hour: int, minute: int,
              seconds: float, calendar: str = GREGORIAN
              ) -> tuple[float, float]:
    """Civil UTC instant → (jd_tt, jd_ut1).  swe_utc_to_jd semantics.

    ``seconds`` may reach into [60, 61) during an inserted leap second.

    Era rules (measured SE 2.10.03 behaviour, see _to_delete-era probes and
    tests/kernel/fixtures):

    * before 1972: no leap-second UTC existed — civil time is UT1
      (documented in the SE programmer manual §9.3).
    * 1972 .. leap-table horizon: TT via TAI, UT1 via ΔT.
    * far future: once the frozen leap table would imply UT1−UTC < −1 s
      (ΔT − dAT − 32.184 > 1, reached during 2033 for SE 2.10.03), SE
      falls back to interpreting civil time as UT1 (with a ~1 s step in
      TT at the flip, which we replicate).
    """
    day_jd = julday(year, month, day, 0.0, calendar)
    sec_of_day = hour * 3600.0 + minute * 60.0 + seconds
    utc_mode = day_jd >= _UTC_ERA_START
    if utc_mode:
        dat = tai_minus_utc(day_jd)
        if deltat_sec(day_jd, "jpleph") - dat - TT_MINUS_TAI > 1.0:
            utc_mode = False
    if utc_mode:
        jd_tt = day_jd + (sec_of_day + dat + TT_MINUS_TAI) / 86400.0
        jd_ut1 = tt_to_ut1(jd_tt, "jpleph")
    else:
        jd_ut1 = day_jd + sec_of_day / 86400.0
        jd_tt = jd_ut1 + deltat_sec(jd_ut1, "jpleph") / 86400.0
    return jd_tt, jd_ut1
