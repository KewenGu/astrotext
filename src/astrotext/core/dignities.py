"""Essential dignities — classical tables with sources.

Tables:
  DOMICILE      standard rulerships (Ptolemy, Tetrabiblos I.17)
  EXALTATION    with traditional degrees (Tetrabiblos I.19; degrees per
                Dorotheus/Valens tradition)
  TRIPLICITY    Dorothean day/night/participating rulers (Dorotheus I.1)
  BOUNDS        Egyptian terms (Valens/Dorotheus; the astro.com default set)
  DECANS        faces in Chaldean order starting Aries I = Mars

Scoring (Lilly-style weights, documented not hidden):
  domicile +5, exaltation +4, triplicity +3 (any of the three rulers),
  bound +2, decan +1, detriment -5, fall -4.
  A planet with no essential dignity at its own position is peregrine.

Only the classical seven receive dignity assessment; outer planets and
points get '-' (they have no seats in the traditional scheme).
"""
from __future__ import annotations

from dataclasses import dataclass

from .zodiac import deg_in_sign, sign_index

__all__ = [
    "DOMICILE", "EXALTATION", "FALL", "DETRIMENT", "TRIPLICITY",
    "BOUNDS_EGYPTIAN", "DECANS_CHALDEAN", "SCORE_WEIGHTS",
    "DignityRecord", "assess", "sign_ruler", "receptions",
]

S = ["SUN", "MOON", "MERCURY", "VENUS", "MARS", "JUPITER", "SATURN"]

# sign index 0=Aries .. 11=Pisces
DOMICILE = ["MARS", "VENUS", "MERCURY", "MOON", "SUN", "MERCURY",
            "VENUS", "MARS", "JUPITER", "SATURN", "SATURN", "JUPITER"]

#: planet -> (sign, traditional degree) ; degree is the culminating degree
EXALTATION: dict[str, tuple[int, int]] = {
    "SUN": (0, 19), "MOON": (1, 3), "MERCURY": (5, 15), "VENUS": (11, 27),
    "MARS": (9, 28), "JUPITER": (3, 15), "SATURN": (6, 21),
}
#: derived: sign -> exalted planet
EXALTED_IN = {sign: p for p, (sign, _deg) in EXALTATION.items()}
#: fall = sign opposite exaltation, detriment = sign opposite domicile
FALL = {p: (sign + 6) % 12 for p, (sign, _d) in EXALTATION.items()}
DETRIMENT: dict[int, str] = {(i + 6) % 12: DOMICILE[i] for i in range(12)}

#: Dorothean triplicities: element -> (day, night, participating)
TRIPLICITY: dict[str, tuple[str, str, str]] = {
    "fire":  ("SUN", "JUPITER", "SATURN"),
    "earth": ("VENUS", "MOON", "MARS"),
    "air":   ("SATURN", "MERCURY", "JUPITER"),
    "water": ("VENUS", "MARS", "MOON"),
}

#: Egyptian bounds: per sign, list of (upper-limit-degree, planet).
#: Each sign's spans sum to 30 and use the five non-luminaries exactly once.
BOUNDS_EGYPTIAN: list[list[tuple[int, str]]] = [
    [(6, "JUPITER"), (12, "VENUS"), (20, "MERCURY"), (25, "MARS"), (30, "SATURN")],   # Ari
    [(8, "VENUS"), (14, "MERCURY"), (22, "JUPITER"), (27, "SATURN"), (30, "MARS")],   # Tau
    [(6, "MERCURY"), (12, "JUPITER"), (17, "VENUS"), (24, "MARS"), (30, "SATURN")],   # Gem
    [(7, "MARS"), (13, "VENUS"), (19, "MERCURY"), (26, "JUPITER"), (30, "SATURN")],   # Can
    [(6, "JUPITER"), (11, "VENUS"), (18, "SATURN"), (24, "MERCURY"), (30, "MARS")],   # Leo
    [(7, "MERCURY"), (17, "VENUS"), (21, "JUPITER"), (28, "MARS"), (30, "SATURN")],   # Vir
    [(6, "SATURN"), (14, "MERCURY"), (21, "JUPITER"), (28, "VENUS"), (30, "MARS")],   # Lib
    [(7, "MARS"), (11, "VENUS"), (19, "MERCURY"), (24, "JUPITER"), (30, "SATURN")],   # Sco
    [(12, "JUPITER"), (17, "VENUS"), (21, "MERCURY"), (26, "SATURN"), (30, "MARS")],  # Sag
    [(7, "MERCURY"), (14, "JUPITER"), (22, "VENUS"), (26, "SATURN"), (30, "MARS")],   # Cap
    [(7, "MERCURY"), (13, "VENUS"), (20, "JUPITER"), (25, "MARS"), (30, "SATURN")],   # Aqu
    [(12, "VENUS"), (16, "JUPITER"), (19, "MERCURY"), (28, "MARS"), (30, "SATURN")],  # Pis
]

#: Chaldean order for decans/faces, Aries I = Mars, descending sequence
_CHALDEAN = ["MARS", "SUN", "VENUS", "MERCURY", "MOON", "SATURN", "JUPITER"]
DECANS_CHALDEAN: list[list[str]] = [
    [_CHALDEAN[(i * 3 + j) % 7] for j in range(3)] for i in range(12)
]

SCORE_WEIGHTS = {"domicile": 5, "exaltation": 4, "triplicity": 3,
                 "bound": 2, "decan": 1, "detriment": -5, "fall": -4}

_ELEMENT_OF_SIGN = ["fire", "earth", "air", "water"]


@dataclass(frozen=True, slots=True)
class DignityRecord:
    planet: str
    sign: int
    dignities: tuple[str, ...]     # subset of SCORE_WEIGHTS keys, deterministic order
    score: int
    peregrine: bool
    bound_ruler: str
    decan_ruler: str
    triplicity_rulers: tuple[str, str, str]
    sign_ruler: str
    exalted_here: str | None


def sign_ruler(sign: int) -> str:
    return DOMICILE[sign]


def bound_ruler(lon: float) -> str:
    sign, deg = sign_index(lon), deg_in_sign(lon)
    for limit, planet in BOUNDS_EGYPTIAN[sign]:
        if deg < limit:
            return planet
    return BOUNDS_EGYPTIAN[sign][-1][1]  # deg == 30.0 impossible after norm


def decan_ruler(lon: float) -> str:
    return DECANS_CHALDEAN[sign_index(lon)][min(2, int(deg_in_sign(lon) // 10))]


def assess(planet: str, lon: float, is_day: bool) -> DignityRecord | None:
    """Essential dignity of one of the classical seven at a longitude.
    Returns None for planets outside the traditional scheme."""
    if planet not in S:
        return None
    sign = sign_index(lon)
    element = _ELEMENT_OF_SIGN[sign % 4]
    trip = TRIPLICITY[element]
    b_ruler = bound_ruler(lon)
    d_ruler = decan_ruler(lon)

    found: list[str] = []
    if DOMICILE[sign] == planet:
        found.append("domicile")
    if EXALTED_IN.get(sign) == planet:
        found.append("exaltation")
    trip_ruler = trip[0] if is_day else trip[1]
    if planet in (trip_ruler, trip[2]):
        found.append("triplicity")
    if b_ruler == planet:
        found.append("bound")
    if d_ruler == planet:
        found.append("decan")
    if DETRIMENT.get(sign) == planet:
        found.append("detriment")
    if planet in FALL and FALL[planet] == sign:
        found.append("fall")

    score = sum(SCORE_WEIGHTS[d] for d in found)
    positive = [d for d in found if SCORE_WEIGHTS[d] > 0]
    return DignityRecord(
        planet=planet, sign=sign, dignities=tuple(found), score=score,
        peregrine=not positive,
        bound_ruler=b_ruler, decan_ruler=d_ruler,
        triplicity_rulers=trip, sign_ruler=DOMICILE[sign],
        exalted_here=EXALTED_IN.get(sign),
    )


def receptions(longitudes: dict[str, float], is_day: bool
               ) -> list[tuple[str, str, str]]:
    """Mutual receptions among the classical seven.

    Returns (planet_a, planet_b, kind) with kind in
    {'domicile', 'exaltation', 'mixed'} — a is received by b and b by a.
    Deterministic order: by planet order in S.
    """
    def dignities_held(host_sign: int) -> dict[str, str]:
        """planet -> strongest dignity it holds over host_sign."""
        out: dict[str, str] = {}
        out[DOMICILE[host_sign]] = "domicile"
        ex = EXALTED_IN.get(host_sign)
        if ex and ex not in out:
            out[ex] = "exaltation"
        return out

    res: list[tuple[str, str, str]] = []
    present = [p for p in S if p in longitudes]
    for i, a in enumerate(present):
        for b in present[i + 1:]:
            da = dignities_held(sign_index(longitudes[a]))  # who rules a's sign
            db = dignities_held(sign_index(longitudes[b]))
            if b in da and a in db:
                ka, kb = da[b], db[a]
                kind = ka if ka == kb else "mixed"
                res.append((a, b, kind))
    return res
