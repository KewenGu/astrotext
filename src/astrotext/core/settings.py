"""Chart settings — every choice that changes numbers is HERE, explicit,
and echoed into every rendered output (design axiom #5).

Nothing in the engine reads a hidden default: if a school disagrees on a
value (orbs, house system, node type...), it becomes a field with the
mainstream default and a docstring citing the alternative.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from ..ephem.points import ORDER

__all__ = ["AspectDef", "Settings", "MODERN", "HELLENISTIC"]


@dataclass(frozen=True, slots=True)
class AspectDef:
    key: str          # "conjunction"
    abbr: str         # "con"
    angle: float      # 0, 60, 90, ...
    orb: float        # base orb, degrees
    orb_luminary: float  # orb when Sun or Moon participates
    major: bool


MAJOR_ASPECTS: tuple[AspectDef, ...] = (
    AspectDef("conjunction", "con", 0.0, 8.0, 10.0, True),
    AspectDef("sextile", "sex", 60.0, 5.0, 6.0, True),
    AspectDef("square", "squ", 90.0, 7.0, 8.0, True),
    AspectDef("trine", "tri", 120.0, 7.0, 8.0, True),
    AspectDef("opposition", "opp", 180.0, 8.0, 10.0, True),
)

MINOR_ASPECTS: tuple[AspectDef, ...] = (
    AspectDef("semisextile", "ssx", 30.0, 2.0, 2.0, False),
    AspectDef("semisquare", "ssq", 45.0, 2.0, 2.0, False),
    AspectDef("sesquiquadrate", "sqq", 135.0, 2.0, 2.0, False),
    AspectDef("quincunx", "qcx", 150.0, 2.5, 2.5, False),
)


@dataclass(frozen=True, slots=True)
class Settings:
    """All knobs for one chart computation.

    zodiac        'tropical' now; 'sidereal:<ayanamsa>' arrives with the
                  Vedic layer (M5) as a flag on the same pipeline.
    house_system  Swiss Ephemeris letter: P Placidus, W whole-sign, K Koch,
                  O Porphyry, R Regiomontanus, C Campanus, A equal, B Alcabitius
    polar_fallback house system used when the primary fails beyond the polar
                  circles (Placidus/Koch raise there); 'O' Porphyry by default
                  — the same substitution Swiss Ephemeris/astro.com make, but
                  we FLAG it instead of switching silently.
    points        computed points, canonical order
    angle_points  angles that participate in aspects (with angle_orb)
    aspects       aspect definitions in use
    node          'true' or 'mean' — which node pair is listed among points
    unknown_time  birth time unknown: noon chart, houses/angles suppressed,
                  Moon flagged (moves ~13 deg/day)
    """

    zodiac: str = "tropical"
    house_system: str = "P"
    polar_fallback: str = "O"
    points: tuple[str, ...] = tuple(k for k in ORDER if k not in ("MEAN_NODE", "SOUTH_NODE_MEAN"))
    angle_points: tuple[str, ...] = ("ASC", "MC")
    angle_orb: float = 3.0
    aspects: tuple[AspectDef, ...] = MAJOR_ASPECTS + MINOR_ASPECTS
    aspect_points: tuple[str, ...] | None = None  # None => all points
    node: str = "true"
    unknown_time: bool = False
    fixed_star_orb: float = 1.0
    antiscia_orb: float = 1.0

    def describe(self) -> list[str]:
        """Deterministic key=value lines for output headers."""
        asp = ",".join(f"{a.abbr}{a.angle:g}:{a.orb:g}/{a.orb_luminary:g}" for a in self.aspects)
        return [
            f"zodiac={self.zodiac}",
            f"houses={self.house_system}(polar-fallback={self.polar_fallback})",
            f"points={','.join(self.points)}",
            f"angle-aspects={','.join(self.angle_points)}@{self.angle_orb:g}",
            f"aspects={asp}",
            f"node={self.node}",
            f"unknown-time={str(self.unknown_time).lower()}",
            f"star-orb={self.fixed_star_orb:g} antiscia-orb={self.antiscia_orb:g}",
        ]

    def with_(self, **kw) -> "Settings":
        return replace(self, **kw)


#: modern western default (astro.com-like): Placidus, true node, majors+minors
MODERN = Settings()

#: hellenistic: whole-sign houses, classical seven + nodes, majors only,
#: sign-based thinking (orbs kept as moieties for the aspect list)
HELLENISTIC = Settings(
    house_system="W",
    points=("SUN", "MOON", "MERCURY", "VENUS", "MARS", "JUPITER", "SATURN",
            "TRUE_NODE", "SOUTH_NODE_TRUE"),
    aspects=MAJOR_ASPECTS,
)
