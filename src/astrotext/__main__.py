"""CLI:  python -m astrotext --help

Example:
  python -m astrotext dossier \
    --name "Kewen" --birth "1990-01-02 13:45" --lat 39.9042 --lon 116.4074 \
    --tz Asia/Shanghai --now "2026-07-08 12:00" \
    --cur-lat 40.7128 --cur-lon -74.0060 --cur-name "New York" \
    --out ./dossiers

Notes:
  --birth is LOCAL civil time at the birth place; --now is UTC.
  --tz accepts an IANA name, 'LMT', or a fixed 'UTC+HH:MM'.
  --unknown-time renders a noon chart without houses/angles/lots.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys


def _dt_arg(s: str) -> dt.datetime:
    s = s.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"bad datetime {s!r}; use 'YYYY-MM-DD HH:MM'")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="astrotext",
        description="Plain-text astrology dossiers for AI agents (Swiss Ephemeris)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("dossier", help="generate a full dossier directory")
    d.add_argument("--name", required=True)
    d.add_argument("--birth", required=True, type=_dt_arg,
                   help="local civil birth time 'YYYY-MM-DD HH:MM'")
    d.add_argument("--lat", type=float, default=None)
    d.add_argument("--lon", type=float, default=None,
                   help="east positive, west negative")
    d.add_argument("--tz", default=None,
                   help="IANA zone | LMT | UTC+HH:MM")
    d.add_argument("--place-name", default=None)
    d.add_argument("--birth-place", default=None,
                   help="place name (Chinese OK: 北京/纽约); resolved via the "
                        "offline gazetteer instead of --lat/--lon/--tz")
    d.add_argument("--birth-country", default=None,
                   help="ISO-2 code or country name to disambiguate")
    d.add_argument("--calendar", choices=["gregorian", "julian"],
                   default="gregorian")
    d.add_argument("--fold", type=int, choices=[0, 1], default=0,
                   help="ambiguous local time: 0=first occurrence, 1=second")
    d.add_argument("--unknown-time", action="store_true")
    d.add_argument("--now", required=True, type=_dt_arg,
                   help="target moment, UTC, 'YYYY-MM-DD HH:MM'")
    d.add_argument("--cur-lat", type=float, default=None)
    d.add_argument("--cur-lon", type=float, default=None)
    d.add_argument("--cur-name", default=None)
    d.add_argument("--cur-place", default=None,
                   help="current location by name (gazetteer)")
    d.add_argument("--cur-country", default=None)
    d.add_argument("--out", default="./dossiers")
    d.add_argument("--format", choices=["text", "json", "both"], default="both",
                   help="text=LLM-context view, json=pipeline view (full precision)")

    v = sub.add_parser("verify", help="run the verification report")
    sub.add_parser("mcp", help="run the MCP stdio server (tools for AI agents)")
    h = sub.add_parser("http", help="run the HTTP facade (REST-ish, localhost)")
    h.add_argument("--host", default="127.0.0.1")
    h.add_argument("--port", type=int, default=8747)

    args = ap.parse_args(argv)

    if args.cmd == "verify":
        from .verify.report import main as vmain
        return vmain()
    if args.cmd == "mcp":
        from .mcp_server import main as mmain
        return mmain()
    if args.cmd == "http":
        from .http_server import serve
        return serve(args.host, args.port)

    from .dossier import Subject, generate_dossier
    from .timespace import Place

    notes: list[str] = []
    if args.birth_place:
        from .timespace.gazetteer import resolve_place
        bplace, bflags = resolve_place(args.birth_place, args.birth_country)
        notes += list(bflags)
        if args.tz:  # explicit tz overrides the gazetteer's
            bplace = Place(bplace.lat, bplace.lon, bplace.name, args.tz)
    else:
        if args.lat is None or args.lon is None or args.tz is None:
            ap.error("either --birth-place OR all of --lat/--lon/--tz required")
        bplace = Place(args.lat, args.lon, args.place_name, args.tz)

    if args.cur_place:
        from .timespace.gazetteer import resolve_place
        cplace, cflags = resolve_place(args.cur_place, args.cur_country)
        notes += [f"current-{f}" for f in cflags]
    else:
        if args.cur_lat is None or args.cur_lon is None:
            ap.error("either --cur-place OR --cur-lat/--cur-lon required")
        cplace = Place(args.cur_lat, args.cur_lon, args.cur_name)

    subject = Subject(
        name=args.name, local=args.birth, place=bplace,
        calendar=args.calendar, fold=args.fold,
        unknown_time=args.unknown_time, notes=tuple(notes),
    )
    slug = re.sub(r"[^a-z0-9]+", "-", args.name.lower()).strip("-") or "subject"
    out = generate_dossier(
        subject,
        now_utc=args.now.replace(tzinfo=dt.timezone.utc),
        current_place=cplace,
        out_dir=f"{args.out}/{slug}",
        fmt=args.format,
    )
    n = len(list(out.glob("*.txt")))
    print(f"dossier written: {out}  ({n} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
