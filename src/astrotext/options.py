"""Request-level settings for the REST/MCP facades.

One JSON object controls every number-changing knob, strictly validated:
unknown keys or values are 400-errors, never silently ignored (axiom #2 —
a typo like "hous_system" must not quietly fall back to Placidus).

Shape (all keys optional; defaults = the documented mainstream):

    "settings": {
      "house_system": "P|W|K|O|R|C|A|B",       # Placidus default
      "polar_fallback": "O|W|A",                # Porphyry default
      "node": "true|mean",                      # western node pair
      "aspects": "majors|majors+minors",
      "angle_orb": 3.0,                         # ASC/MC aspect orb, deg
      "transit_orb": 3.0,
      "transit_window_days": 400,
      "progression_year": "tropical|julian",
      "progression_month": "tropical|sidereal",
      "return_precessed": false,
      "firdaria_nodes": "after-mars|at-end",
      "vedic": {
        "ayanamsa": "lahiri|krishnamurti|raman|fagan-bradley",
        "node": "mean|true",
        "karaka_scheme": 8,                     # or 7
        "dasha_year_days": 365.25,
        "dasha_max_level": 3,                   # 1..3
        "vargas": [1, 9, 10]                    # subset of the 16
      }
    }

The parsed result is (Settings, VedicSettings, TechOptions) — the same
frozen objects the Python API uses, so facade calls and library calls are
provably identical.
"""
from __future__ import annotations

from dataclasses import dataclass

from .core.settings import MAJOR_ASPECTS, MINOR_ASPECTS, MODERN, Settings
from .techniques.vedic.sidereal import VedicSettings
from .techniques.vedic.vargas import VARGA_NAMES

__all__ = ["TechOptions", "parse_settings", "settings_cache_key"]

_HOUSE_SYSTEMS = set("PWKORCAB")
_W_KEYS = {"house_system", "polar_fallback", "node", "aspects", "angle_orb",
           "transit_orb", "transit_window_days", "progression_year",
           "progression_month", "return_precessed", "firdaria_nodes",
           "vedic"}
_V_KEYS = {"ayanamsa", "node", "karaka_scheme", "dasha_year_days",
           "dasha_max_level", "vargas"}
_AYANAMSAS = {"lahiri", "krishnamurti", "raman", "fagan-bradley"}


@dataclass(frozen=True, slots=True)
class TechOptions:
    """Technique-level knobs that live outside chart Settings."""

    transit_orb: float = 3.0
    transit_window_days: float = 400.0
    progression_year: str = "tropical"
    progression_month: str = "tropical"
    return_precessed: bool = False
    firdaria_nodes: str = "after-mars"
    dasha_max_level: int = 3


def _fail(msg: str) -> None:
    raise ValueError(f"settings: {msg}")


def _enum(d: dict, key: str, allowed: set[str] | tuple[str, ...]) -> str | None:
    if key not in d:
        return None
    v = d[key]
    if not isinstance(v, str) or v not in allowed:
        _fail(f"{key} must be one of {sorted(allowed)}, got {v!r}")
    return v


def _number(d: dict, key: str, lo: float, hi: float) -> float | None:
    if key not in d:
        return None
    v = d[key]
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
        _fail(f"{key} must be a number in [{lo}, {hi}], got {v!r}")
    return float(v)


def parse_settings(raw: dict | None
                   ) -> tuple[Settings, VedicSettings, TechOptions]:
    """Validate a request settings dict into the engine's frozen objects."""
    if raw is None:
        return MODERN, VedicSettings(), TechOptions()
    if not isinstance(raw, dict):
        _fail("must be a JSON object")

    unknown = set(raw) - _W_KEYS
    if unknown:
        _fail(f"unknown keys {sorted(unknown)}; allowed: {sorted(_W_KEYS)}")

    s_kw: dict = {}
    if (v := _enum(raw, "house_system", _HOUSE_SYSTEMS)) is not None:
        s_kw["house_system"] = v
    if (v := _enum(raw, "polar_fallback", {"O", "W", "A"})) is not None:
        s_kw["polar_fallback"] = v
    if (v := _enum(raw, "node", {"true", "mean"})) is not None:
        s_kw["node"] = v
        pts = list(MODERN.points)
        if v == "mean":
            pts = ["MEAN_NODE" if p == "TRUE_NODE" else
                   "SOUTH_NODE_MEAN" if p == "SOUTH_NODE_TRUE" else p
                   for p in pts]
        s_kw["points"] = tuple(pts)
    if (v := _enum(raw, "aspects", {"majors", "majors+minors"})) is not None:
        s_kw["aspects"] = (MAJOR_ASPECTS if v == "majors"
                           else MAJOR_ASPECTS + MINOR_ASPECTS)
    if (v := _number(raw, "angle_orb", 0.0, 10.0)) is not None:
        s_kw["angle_orb"] = v
    settings = MODERN.with_(**s_kw) if s_kw else MODERN

    t_kw: dict = {}
    if (v := _number(raw, "transit_orb", 0.1, 10.0)) is not None:
        t_kw["transit_orb"] = v
    if (v := _number(raw, "transit_window_days", 1.0, 2000.0)) is not None:
        t_kw["transit_window_days"] = v
    if (v := _enum(raw, "progression_year", {"tropical", "julian"})) is not None:
        t_kw["progression_year"] = v
    if (v := _enum(raw, "progression_month", {"tropical", "sidereal"})) is not None:
        t_kw["progression_month"] = v
    if "return_precessed" in raw:
        if not isinstance(raw["return_precessed"], bool):
            _fail("return_precessed must be true/false")
        t_kw["return_precessed"] = raw["return_precessed"]
    if (v := _enum(raw, "firdaria_nodes", {"after-mars", "at-end"})) is not None:
        t_kw["firdaria_nodes"] = v

    v_kw: dict = {}
    vraw = raw.get("vedic")
    if vraw is not None:
        if not isinstance(vraw, dict):
            _fail("vedic must be a JSON object")
        vunknown = set(vraw) - _V_KEYS
        if vunknown:
            _fail(f"unknown vedic keys {sorted(vunknown)}; "
                  f"allowed: {sorted(_V_KEYS)}")
        if (v := _enum(vraw, "ayanamsa", _AYANAMSAS)) is not None:
            v_kw["ayanamsa"] = v
        if (v := _enum(vraw, "node", {"mean", "true"})) is not None:
            v_kw["node"] = v
        if "karaka_scheme" in vraw:
            if vraw["karaka_scheme"] not in (7, 8):
                _fail("vedic.karaka_scheme must be 7 or 8")
            v_kw["karaka_scheme"] = vraw["karaka_scheme"]
        if (v := _number(vraw, "dasha_year_days", 350.0, 370.0)) is not None:
            v_kw["dasha_year_days"] = v
        if "dasha_max_level" in vraw:
            if vraw["dasha_max_level"] not in (1, 2, 3):
                _fail("vedic.dasha_max_level must be 1, 2, or 3")
            t_kw["dasha_max_level"] = vraw["dasha_max_level"]
        if "vargas" in vraw:
            vs = vraw["vargas"]
            if (not isinstance(vs, list) or not vs
                    or any(x not in VARGA_NAMES for x in vs)):
                _fail(f"vedic.vargas must be a non-empty subset of "
                      f"{sorted(VARGA_NAMES)}")
            v_kw["vargas"] = tuple(sorted(set(vs)))

    vedic = VedicSettings(**v_kw) if v_kw else VedicSettings()
    tech = TechOptions(**t_kw) if t_kw else TechOptions()
    return settings, vedic, tech


def settings_cache_key(raw: dict | None) -> str:
    """Canonical string form for LRU keys (validates as a side effect)."""
    parse_settings(raw)
    import json
    return json.dumps(raw or {}, sort_keys=True, separators=(",", ":"))
