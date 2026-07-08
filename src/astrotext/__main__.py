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
    d.add_argument("--lat", required=True, type=float)
    d.add_argument("--lon", required=True, type=float,
                   help="east positive, west negative")
    d.add_argument("--tz", required=True,
                   help="IANA zone | LMT | UTC+HH:MM")
    d.add_argument("--place-name", default=None)
    d.add_argument("--calendar", choices=["gregorian", "julian"],
                   default="gregorian")
    d.add_argument("--fold", type=int, choices=[0, 1], default=0,
                   help="ambiguous local time: 0=first occurrence, 1=second")
    d.add_argument("--unknown-time", action="store_true")
    d.add_argument("--now", required=True, type=_dt_arg,
                   help="target moment, UTC, 'YYYY-MM-DD HH:MM'")
    d.add_argument("--cur-lat", required=True, type=float)
    d.add_argument("--cur-lon", required=True, type=float)
    d.add_argument("--cur-name", default=None)
    d.add_argument("--out", default="./dossiers")

    v = sub.add_parser("verify", help="run the verification report")

    args = ap.parse_args(argv)

    if args.cmd == "verify":
        from .verify.report import main as vmain
        return vmain()

    from .dossier import Subject, generate_dossier
    from .timespace import Place

    subject = Subject(
        name=args.name, local=args.birth,
        place=Place(args.lat, args.lon, args.place_name, args.tz),
        calendar=args.calendar, fold=args.fold,
        unknown_time=args.unknown_time,
    )
    slug = re.sub(r"[^a-z0-9]+", "-", args.name.lower()).strip("-") or "subject"
    out = generate_dossier(
        subject,
        now_utc=args.now.replace(tzinfo=dt.timezone.utc),
        current_place=Place(args.cur_lat, args.cur_lon, args.cur_name),
        out_dir=f"{args.out}/{slug}",
    )
    n = len(list(out.glob("*.txt")))
    print(f"dossier written: {out}  ({n} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
