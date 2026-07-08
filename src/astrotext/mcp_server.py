"""MCP server (stdio) — expose the chart engine to AI agents as tools.

Zero-dependency implementation of the Model Context Protocol stdio
transport: JSON-RPC 2.0, one JSON object per line on stdin/stdout
(protocol revision 2024-11-05; also answers newer clients that send a
different protocolVersion by echoing our supported one).

Run:  python -m astrotext mcp
Client config (e.g. Claude Code / desktop):
  { "command": "python3", "args": ["-m", "astrotext", "mcp"],
    "env": { "PYTHONPATH": "<repo>/src:<repo>/vendor/py:<repo>/vendor/lib",
             "SE_EPHE_PATH": "<repo>/data/ephe" } }

Tools:
  astro_chart    one chart/report as plain text (or JSON view)
  astro_dossier  the complete dossier; returns index + requested files

Design notes: subjects are passed per-call (stateless server); results are
the same deterministic texts the CLI writes.  A small LRU keyed on the
full input tuple makes "one dossier, many chart pulls" cheap.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from functools import lru_cache

from . import ENGINE_NAME, __version__

PROTOCOL_VERSION = "2024-11-05"

_KINDS = ["natal", "natal_hellenistic", "transits", "secondary", "tertiary",
          "solar_arc", "solar_return", "lunar_return", "firdaria",
          "profections", "vedic_rashi", "vedic_vargas", "vedic_vimshottari"]

_STEM = {
    "natal": "10_natal", "natal_hellenistic": "11_natal_hellenistic",
    "transits": "20_transits", "secondary": "21_secondary",
    "tertiary": "22_tertiary", "solar_arc": "23_solar_arc",
    "solar_return": "30_solar_return", "lunar_return": "31_lunar_return",
    "firdaria": "40_firdaria", "profections": "41_profections",
    "vedic_rashi": "50_vedic_rashi", "vedic_vargas": "51_vedic_vargas",
    "vedic_vimshottari": "52_vedic_vimshottari",
}

_SUBJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "birth": {"type": "string",
                  "description": "local civil birth time 'YYYY-MM-DD HH:MM'"},
        "lat": {"type": "number", "description": "birth latitude, north+"},
        "lon": {"type": "number", "description": "birth longitude, east+"},
        "tz": {"type": "string",
               "description": "IANA zone | 'LMT' | 'UTC+HH:MM'"},
        "place_name": {"type": "string"},
        "calendar": {"type": "string", "enum": ["gregorian", "julian"]},
        "fold": {"type": "integer", "enum": [0, 1],
                 "description": "ambiguous local time: 0 first, 1 second"},
        "unknown_time": {"type": "boolean"},
    },
    "required": ["birth", "lat", "lon", "tz"],
}

_CURRENT_SCHEMA = {
    "type": "object",
    "properties": {
        "lat": {"type": "number"}, "lon": {"type": "number"},
        "name": {"type": "string"},
    },
    "required": ["lat", "lon"],
}

TOOLS = [
    {
        "name": "astro_chart",
        "description": (
            "Compute one astrological chart/report as verifiable plain text "
            "(Swiss Ephemeris engine). Every number is precomputed — do not "
            "re-derive positions or orbs. Timestamps are UTC. kinds: "
            + ", ".join(_KINDS)),
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": _KINDS},
                "subject": _SUBJECT_SCHEMA,
                "now": {"type": "string",
                        "description": "target moment UTC 'YYYY-MM-DD HH:MM' "
                                       "(required for timed kinds; defaults "
                                       "to birth for natal-only kinds)"},
                "current": _CURRENT_SCHEMA,
                "format": {"type": "string", "enum": ["text", "json"],
                           "default": "text"},
                "settings": {"type": "object",
                             "description": "optional knobs: house_system "
                             "P|W|K|O|R|C|A|B, node true|mean, aspects, "
                             "angle_orb, transit_orb, transit_window_days, "
                             "progression_year|month, return_precessed, "
                             "firdaria_nodes, vedic{ayanamsa,node,"
                             "karaka_scheme,dasha_year_days,dasha_max_level,"
                             "vargas} — see docs/API.md; unknown keys are "
                             "rejected"},
            },
            "required": ["kind", "subject"],
        },
    },
    {
        "name": "astro_resolve_place",
        "description": (
            "Resolve a place name (Chinese OK: 北京/纽约/兰州) to coordinates "
            "and IANA timezone via the offline GeoNames gazetteer. Use before "
            "astro_chart/astro_dossier when you only have a place name. "
            "Returns ranked candidates; ambiguity means you should pass "
            "country or confirm with the user."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "country": {"type": "string",
                            "description": "ISO-2 code or country name"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "astro_dossier",
        "description": (
            "Generate a person's COMPLETE astrological dossier (natal modern"
            "+hellenistic, transits with exact timestamps, progressions, "
            "solar arc, solar/lunar returns, firdaria, profections, vedic "
            "rashi/vargas/vimshottari). Returns the reading index plus the "
            "requested files as plain text."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "subject": _SUBJECT_SCHEMA,
                "now": {"type": "string",
                        "description": "target moment UTC 'YYYY-MM-DD HH:MM'"},
                "current": _CURRENT_SCHEMA,
                "include": {"type": "array", "items": {"type": "string"},
                            "description": "chart kinds to include (default: "
                                           "all); index+meta always included"},
                "settings": {"type": "object",
                             "description": "same knobs as astro_chart"},
            },
            "required": ["subject", "now", "current"],
        },
    },
]


def _parse_dt(s: str) -> dt.datetime:
    s = s.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"bad datetime {s!r}; use 'YYYY-MM-DD HH:MM'")


@lru_cache(maxsize=32)
def _dossier_cached(subject_key: tuple, now_s: str, cur_key: tuple,
                    fmt: str, settings_json: str = "{}") -> dict[str, str]:
    import json as _json

    from .dossier import Subject, build_dossier
    from .options import parse_settings
    from .timespace import Place
    name, birth, lat, lon, tz, place_name, calendar, fold, unknown = subject_key
    subject = Subject(
        name=name or "Subject", local=_parse_dt(birth),
        place=Place(lat, lon, place_name, tz),
        calendar=calendar, fold=fold, unknown_time=unknown,
    )
    clat, clon, cname = cur_key
    settings, vedic, tech = parse_settings(_json.loads(settings_json) or None)
    if unknown:
        settings = settings.with_(unknown_time=True)
    return build_dossier(
        subject, _parse_dt(now_s).replace(tzinfo=dt.timezone.utc),
        Place(clat, clon, cname), settings=settings, fmt=fmt,
        vedic_settings=vedic, tech=tech,
    )


def _subject_key(s: dict) -> tuple:
    return (s.get("name"), s["birth"], float(s["lat"]), float(s["lon"]),
            s["tz"], s.get("place_name"), s.get("calendar", "gregorian"),
            int(s.get("fold", 0)), bool(s.get("unknown_time", False)))


def _call_astro_chart(args: dict) -> str:
    kind = args["kind"]
    if kind not in _KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    fmt = args.get("format", "text")
    subject = args["subject"]
    now = args.get("now") or subject["birth"] + ""  # natal kinds: birth moment
    if kind not in ("natal", "natal_hellenistic", "vedic_rashi",
                    "vedic_vargas") and not args.get("now"):
        raise ValueError(f"kind {kind!r} needs 'now' (UTC)")
    cur = args.get("current") or {"lat": subject["lat"], "lon": subject["lon"],
                                  "name": subject.get("place_name")}
    from .options import settings_cache_key
    files = _dossier_cached(_subject_key(subject), now,
                            (float(cur["lat"]), float(cur["lon"]),
                             cur.get("name")), "both",
                            settings_cache_key(args.get("settings")))
    ext = "txt" if fmt == "text" else "json"
    fname = f"{_STEM[kind]}.{ext}"
    if fname not in files:
        raise ValueError(f"{kind} unavailable for this subject "
                         f"(unknown birth time suppresses some reports)")
    return files[fname]


def _call_resolve_place(args: dict) -> str:
    from .timespace.gazetteer import lookup
    hits = lookup(args["query"], args.get("country"),
                  int(args.get("limit", 5)))
    if not hits:
        return (f"no match for {args['query']!r}"
                + (f" in {args['country']}" if args.get("country") else "")
                + "; check spelling or pass lat/lon/tz directly")
    lines = ["# rank | place | lat | lon | timezone | population | matched-on"]
    for i, h in enumerate(hits, 1):
        lines.append(f"{i} | {h.label()} | {h.lat:.4f} | {h.lon:.4f} | "
                     f"{h.tz} | {h.population} | {h.matched_on}")
    return "\n".join(lines)


def _call_astro_dossier(args: dict) -> str:
    subject = args["subject"]
    cur = args["current"]
    from .options import settings_cache_key
    files = _dossier_cached(_subject_key(subject), args["now"],
                            (float(cur["lat"]), float(cur["lon"]),
                             cur.get("name")), "text",
                            settings_cache_key(args.get("settings")))
    include = args.get("include")
    stems = ([_STEM[k] for k in include if k in _STEM] if include
             else list(_STEM.values()))
    parts = [files["index.txt"], files["00_meta.txt"]]
    parts += [files[f"{s}.txt"] for s in stems if f"{s}.txt" in files]
    return "\n".join(parts)


def _handle(req: dict) -> dict | None:
    rid = req.get("id")
    method = req.get("method", "")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": ENGINE_NAME, "version": __version__},
        }}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "astro_chart":
                text = _call_astro_chart(args)
            elif name == "astro_dossier":
                text = _call_astro_dossier(args)
            elif name == "astro_resolve_place":
                text = _call_resolve_place(args)
            else:
                raise ValueError(f"unknown tool {name!r}")
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": text}]}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text",
                             "text": f"error: {type(exc).__name__}: {exc}"}],
                "isError": True}}
    if rid is not None:
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
