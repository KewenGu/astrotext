"""Time-domain root finding on angular functions — the shared machinery for
"when is this aspect exact" (transits), returns (solar/lunar/planetary), and
void-of-course computations.

The core problem: find t where g(t) = angdiff(lon_body(t), target) crosses 0,
where g wraps on (-180, 180].  Strategy:

1. March in coarse steps sized well below the body's synodic behavior
   (default: step = min(15 deg / max_speed, span)), recording sign changes
   of g.  Wrap jumps (|Δg| > 180) are NOT crossings and are skipped.
2. Refine each bracketed crossing by bisection to sub-second precision.

Retrograde loops produce multiple roots; callers get them all (sorted) and
pick what they need (first exact hit, the return within a window, ...).
"""
from __future__ import annotations

from collections.abc import Callable

from ..core.angles import angdiff

__all__ = ["angular_roots", "refine_root"]

SEC = 1.0 / 86400.0  # one second in days


def refine_root(g: Callable[[float], float], lo: float, hi: float,
                tol_days: float = 0.05 * SEC, max_iter: int = 128) -> float:
    """Bisection on a bracketed sign change of a wrap-free local segment."""
    glo = g(lo)
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        gm = g(mid)
        if hi - lo < tol_days:
            return mid
        if (glo < 0) == (gm < 0):
            lo, glo = mid, gm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def angular_roots(
    lon_of: Callable[[float], float],
    target: float,
    t0: float,
    t1: float,
    coarse_step: float,
    tol_days: float = 0.05 * SEC,
) -> list[float]:
    """All t in [t0, t1] where lon_of(t) == target (mod 360), ascending.

    ``coarse_step`` must be small enough that the body moves < 180 deg per
    step (use ~15 deg / max_daily_speed).  Handles retrograde re-crossings.
    """
    if t1 <= t0:
        return []

    def g(t: float) -> float:
        return angdiff(lon_of(t), target)

    roots: list[float] = []
    t_prev, g_prev = t0, g(t0)
    if g_prev == 0.0:
        roots.append(t0)
    t = t0
    while t < t1:
        t = min(t + coarse_step, t1)
        g_now = g(t)
        dg = g_now - g_prev
        # a genuine crossing keeps |Δg| small; a wrap jump is ~360
        if abs(dg) < 180.0 and (g_prev < 0) != (g_now < 0):
            roots.append(refine_root(g, t_prev, t, tol_days))
        elif g_now == 0.0:
            roots.append(t)
        t_prev, g_prev = t, g_now
    # dedupe (a root exactly on a step boundary can appear twice)
    out: list[float] = []
    for r in sorted(roots):
        if not out or r - out[-1] > tol_days * 4:
            out.append(r)
    return out
