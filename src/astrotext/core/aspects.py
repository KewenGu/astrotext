"""Aspect engine.

Definitions (documented so every school can check its assumptions):

* separation  u = |shortest arc between two longitudes|, in [0, 180]
* a pair is "in aspect θ" when |u - θ| <= orb(θ, pair)
* orb(θ, pair): the aspect's base orb, or its luminary orb if Sun/Moon is a
  participant; aspects to chart angles use Settings.angle_orb.
* APPLYING vs SEPARATING: the offset |u - θ| is shrinking vs growing right
  now, judged from the pair's instantaneous longitude speeds:
      du/dt = sign(signed_sep) * (v1 - v2),  offset' = sign(u - θ) * du/dt
  applying  <=> offset' < 0.  |u - θ| < EXACT_EPS renders as exact 'E'.
  Angles in a natal chart have no speed (they are frame, not body) — aspects
  to ASC/MC carry '-' instead.

The same engine serves natal, synastry and transit grids: it only sees
(name, lon, speed | None) triples.
"""
from __future__ import annotations

from dataclasses import dataclass

from .angles import angdiff
from .settings import AspectDef, Settings

__all__ = ["AspectHit", "find_aspects"]

EXACT_EPS = 1.0 / 60.0  # within 1 arcmin renders as 'E'

LUMINARIES = {"SUN", "MOON"}


@dataclass(frozen=True, slots=True)
class AspectHit:
    p1: str
    p2: str
    aspect: AspectDef
    separation: float      # u, [0, 180]
    orb_abs: float         # |u - angle|
    orb_signed: float      # u - angle
    phase: str             # 'A' applying | 'S' separating | 'E' exact | '-' n/a
    orb_allowed: float


def _phase(u: float, theta: float, signed_sep: float,
           v1: float | None, v2: float | None) -> str:
    if abs(u - theta) < EXACT_EPS:
        return "E"
    if v1 is None or v2 is None:
        return "-"
    # d(u)/dt where u = |signed_sep|
    du = (1.0 if signed_sep >= 0 else -1.0) * (v1 - v2)
    doffset = (1.0 if u > theta else -1.0) * du
    return "A" if doffset < 0 else "S"


def find_aspects(
    positions: list[tuple[str, float, float | None]],
    settings: Settings,
    pairs_with: list[tuple[str, float, float | None]] | None = None,
) -> list[AspectHit]:
    """All aspect hits among ``positions`` (i<j), or — if ``pairs_with`` is
    given — between each of ``positions`` and each of ``pairs_with`` (the
    transit/synastry grid).  Deterministic order: input order, then aspect
    angle."""
    hits: list[AspectHit] = []

    def check(n1: str, l1: float, v1: float | None,
              n2: str, l2: float, v2: float | None) -> None:
        signed = angdiff(l1, l2)
        u = abs(signed)
        for a in settings.aspects:
            if n1 in settings.angle_points or n2 in settings.angle_points:
                allowed = settings.angle_orb
            elif n1 in LUMINARIES or n2 in LUMINARIES:
                allowed = a.orb_luminary
            else:
                allowed = a.orb
            off = u - a.angle
            if abs(off) <= allowed:
                hits.append(AspectHit(
                    p1=n1, p2=n2, aspect=a, separation=u,
                    orb_abs=abs(off), orb_signed=off,
                    phase=_phase(u, a.angle, signed, v1, v2),
                    orb_allowed=allowed,
                ))

    if pairs_with is None:
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                n1, l1, v1 = positions[i]
                n2, l2, v2 = positions[j]
                check(n1, l1, v1, n2, l2, v2)
    else:
        for n1, l1, v1 in positions:
            for n2, l2, v2 in pairs_with:
                check(n1, l1, v1, n2, l2, v2)
    return hits
