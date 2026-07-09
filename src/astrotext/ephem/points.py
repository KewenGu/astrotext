"""Registry of computable points.

Each point has a stable ``key`` (used everywhere: settings, output, tests),
a body id (Swiss Ephemeris ipl numbering, backend-neutral), English/Chinese labels, and a kind.  Output order
is the canonical ``ORDER`` below — deterministic rendering depends on it.

Derived points (e.g. the South Node = North Node + 180deg, lat negated) are
computed in the core layer, not here; the registry only marks them.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    key: str
    se_id: int | None          # None => derived point (ipl numbering)
    en: str
    zh: str
    kind: str                  # luminary | planet | node | apogee | asteroid | derived
    derived_from: str | None = None


_P = Point

REGISTRY: dict[str, Point] = {p.key: p for p in [
    _P("SUN",        0,        "Sun",         "太阳",   "luminary"),
    _P("MOON",       1,       "Moon",        "月亮",   "luminary"),
    _P("MERCURY",    2,    "Mercury",     "水星",   "planet"),
    _P("VENUS",      3,      "Venus",       "金星",   "planet"),
    _P("MARS",       4,       "Mars",        "火星",   "planet"),
    _P("JUPITER",    5,    "Jupiter",     "木星",   "planet"),
    _P("SATURN",     6,     "Saturn",      "土星",   "planet"),
    _P("URANUS",     7,     "Uranus",      "天王星", "planet"),
    _P("NEPTUNE",    8,    "Neptune",     "海王星", "planet"),
    _P("PLUTO",      9,      "Pluto",       "冥王星", "planet"),
    _P("MEAN_NODE",  10,  "Mean Node",   "北交点(平)", "node"),
    _P("TRUE_NODE",  11,  "True Node",   "北交点(真)", "node"),
    _P("MEAN_APOGEE", 12, "Mean Apogee (Lilith)", "莉莉丝(平)", "apogee"),
    _P("CHIRON",     15,     "Chiron",      "凯龙星", "asteroid"),
    # Derived:
    _P("SOUTH_NODE_MEAN", None, "South Node (mean)", "南交点(平)", "derived", "MEAN_NODE"),
    _P("SOUTH_NODE_TRUE", None, "South Node (true)", "南交点(真)", "derived", "TRUE_NODE"),
]}

#: canonical output order
ORDER: tuple[str, ...] = (
    "SUN", "MOON", "MERCURY", "VENUS", "MARS", "JUPITER", "SATURN",
    "URANUS", "NEPTUNE", "PLUTO",
    "TRUE_NODE", "SOUTH_NODE_TRUE", "MEAN_NODE", "SOUTH_NODE_MEAN",
    "CHIRON", "MEAN_APOGEE",
)

#: the classical seven
CLASSICAL_7: tuple[str, ...] = (
    "SUN", "MOON", "MERCURY", "VENUS", "MARS", "JUPITER", "SATURN",
)

#: Swiss-Ephemeris-computable points (what the L0 engine accepts)
SE_POINTS: tuple[str, ...] = tuple(k for k in ORDER if REGISTRY[k].se_id is not None)


def get(key: str) -> Point:
    try:
        return REGISTRY[key]
    except KeyError:
        raise KeyError(f"unknown point {key!r}; known: {', '.join(sorted(REGISTRY))}") from None
