"""Angle arithmetic on the 360-degree circle.

These few functions underpin every technique in the engine, so they are kept
tiny, exhaustively tested, and free of any dependency.

Conventions
-----------
* Longitudes are ecliptic degrees in [0, 360).
* ``angdiff(a, b)`` is the *signed shortest* arc from ``b`` to ``a`` in
  ``(-180, +180]``.  Invariant: ``norm360(b + angdiff(a, b)) == norm360(a)``
  (up to float error).  At exactly 180 degrees the sign is +.
"""
from __future__ import annotations

import math

__all__ = ["norm360", "angdiff", "deg_to_dms", "dms_to_deg"]


def norm360(x: float) -> float:
    """Normalize an angle to [0, 360)."""
    r = math.fmod(x, 360.0)
    if r < 0.0:
        r += 360.0
    # fmod(-1e-17, 360) + 360 == 360.0 exactly; fold it back.
    return 0.0 if r == 360.0 else r


def angdiff(a: float, b: float) -> float:
    """Signed shortest arc a - b, in (-180, +180]."""
    d = math.fmod(a - b, 360.0)  # (-360, 360)
    if d <= -180.0:
        d += 360.0
    elif d > 180.0:
        d -= 360.0
    return d


def deg_to_dms(x: float, sec_decimals: int = 0) -> tuple[int, int, int, float]:
    """Decompose degrees into (sign, deg, min, sec) with carry-safe rounding.

    ``sign`` is +1 or -1.  Seconds are rounded to ``sec_decimals`` places and
    the carry is propagated so 29d59'59.9995" never renders as 60".
    """
    sign = -1 if x < 0 else 1
    scale = 10 ** sec_decimals
    total = round(abs(x) * 3600.0 * scale)  # integer scaled arcseconds
    sec_scaled = total % (60 * scale)
    total //= 60 * scale
    minutes = total % 60
    degrees = total // 60
    return sign, int(degrees), int(minutes), sec_scaled / scale


def dms_to_deg(sign: int, d: int, m: int, s: float) -> float:
    """Inverse of :func:`deg_to_dms`."""
    return sign * (d + m / 60.0 + s / 3600.0)
