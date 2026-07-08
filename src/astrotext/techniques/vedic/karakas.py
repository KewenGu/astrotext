"""Jaimini chara karakas (movable significators).

Scheme (default 8-karaka, BPHS/Jaimini as practiced today): rank the seven
planets PLUS Rahu by advancement within their sign — planets by degrees
traversed, Rahu REVERSED (30 - deg, it moves backwards) — and assign:

  1 Atmakaraka (AK)    self
  2 Amatyakaraka (AmK) career/minister
  3 Bhratrikaraka (BK) siblings/guru
  4 Matrikaraka (MK)   mother
  5 Pitrikaraka (PiK)  father
  6 Putrakaraka (PuK)  children
  7 Gnatikaraka (GK)   kin/rivals
  8 Darakaraka (DK)    spouse

The 7-karaka variant (planets only, no Rahu, PiK dropped) is available via
``scheme=7``.  Ties (equal degrees) are broken by planet order and flagged.
"""
from __future__ import annotations

from ...core.zodiac import deg_in_sign

__all__ = ["KARAKA_NAMES_8", "KARAKA_NAMES_7", "chara_karakas"]

KARAKA_NAMES_8 = ["AK", "AmK", "BK", "MK", "PiK", "PuK", "GK", "DK"]
KARAKA_NAMES_7 = ["AK", "AmK", "BK", "MK", "PuK", "GK", "DK"]

_PLANETS = ["SUN", "MOON", "MARS", "MERCURY", "JUPITER", "VENUS", "SATURN"]


def chara_karakas(sid_lons: dict[str, float], scheme: int = 8
                  ) -> tuple[list[tuple[str, str, float]], list[str]]:
    """[(karaka, graha, advancement_deg), ...] ranked, plus warning flags.

    ``sid_lons`` must contain the seven planets and (for scheme 8) RAHU.
    """
    if scheme not in (7, 8):
        raise ValueError("karaka scheme must be 7 or 8")
    names = KARAKA_NAMES_8 if scheme == 8 else KARAKA_NAMES_7
    entrants = list(_PLANETS) + (["RAHU"] if scheme == 8 else [])

    adv: list[tuple[float, str]] = []
    for g in entrants:
        d = deg_in_sign(sid_lons[g])
        if g == "RAHU":
            d = 30.0 - d
        adv.append((d, g))

    flags: list[str] = []
    # stable sort: descending advancement, ties broken by entrant order
    order = sorted(range(len(adv)), key=lambda i: (-adv[i][0], i))
    for a in range(len(order) - 1):
        if abs(adv[order[a]][0] - adv[order[a + 1]][0]) < 1e-9:
            flags.append(f"karaka-tie:{adv[order[a]][1]}={adv[order[a+1]][1]}"
                         f"@{adv[order[a]][0]:.6f}deg — order-broken by convention")
    ranked = [(names[i], adv[order[i]][1], adv[order[i]][0])
              for i in range(len(names))]
    return ranked, flags
