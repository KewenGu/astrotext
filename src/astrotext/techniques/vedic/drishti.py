"""Parashari graha drishti (planetary sign aspects), whole-sign.

Every graha fully aspects the 7th sign from itself; additionally
  Mars: 4th and 8th | Jupiter: 5th and 9th | Saturn: 3rd and 10th.
Nodes: BPHS traditions differ (some give Rahu 5/9); DEFAULT: nodes cast no
special drishti (mainstream software default), knob for later.
Counting is inclusive-ordinal: the "7th from" a sign is +6 signs.
"""
from __future__ import annotations

__all__ = ["SPECIAL_DRISHTI", "graha_drishti"]

#: ordinal aspects per graha (7th for all; specials added)
SPECIAL_DRISHTI = {"MARS": (4, 8), "JUPITER": (5, 9), "SATURN": (3, 10)}

_GRAHAS_CASTING = ["SUN", "MOON", "MARS", "MERCURY", "JUPITER",
                   "VENUS", "SATURN"]


def graha_drishti(sign_of: dict[str, int]) -> dict[str, dict[str, object]]:
    """For each casting graha: which SIGNS it aspects and which grahas
    stand in them.  ``sign_of`` maps graha -> sign index 0..11 (must include
    the seven; extra entries like RAHU/KETU are treated as targets only)."""
    out: dict[str, dict[str, object]] = {}
    for g in _GRAHAS_CASTING:
        if g not in sign_of:
            continue
        ordinals = (7,) + SPECIAL_DRISHTI.get(g, ())
        signs = sorted((sign_of[g] + o - 1) % 12 for o in ordinals)
        hit = [t for t, s in sign_of.items() if t != g and s in signs]
        out[g] = {"ordinals": sorted(ordinals), "signs": signs, "grahas": hit}
    return out
