"""Round-trip parser for the astrotext text format (any v<N> header).

Not a consumer API — it exists so tests can prove the rendered text is
faithful: parse(render(chart)) must reproduce every number at the printed
precision.  It is deliberately strict: unknown structure raises.
"""
from __future__ import annotations

import re

__all__ = ["parse"]

_HEADER = re.compile(r"^== ASTROTEXT (\S+) (v\d+) ==$")
_SECTION = re.compile(r"^-- (.+?) --$")
_END = "== END =="


def parse(text: str) -> dict:
    lines = text.splitlines()
    if not lines or not _HEADER.match(lines[0]):
        raise ValueError("not an astrotext chart: bad header")
    kind, version = _HEADER.match(lines[0]).groups()  # type: ignore[union-attr]
    doc: dict = {"kind": kind.lower(), "format": version,
                 "meta": {}, "warnings": [], "settings": {}, "sections": {}}
    section: str | None = None
    for raw in lines[1:]:
        line = raw.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        if line == _END:
            section = "__ended__"
            continue
        m = _SECTION.match(line)
        if m:
            section = m.group(1)
            doc["sections"][section] = []
            continue
        if section is None:
            # meta zone
            if "=" not in line:
                raise ValueError(f"bad meta line: {line!r}")
            key, val = line.split("=", 1)
            if key == "warning":
                if val != "(none)":
                    doc["warnings"].append(val)
            elif key.startswith("set:"):
                doc["settings"][key[4:]] = val
            else:
                doc["meta"][key] = val
            continue
        if section == "__ended__":
            raise ValueError(f"content after END: {line!r}")
        if line == "(none)":
            continue
        row = [f.strip() for f in line.split("|")]
        doc["sections"][section].append(row)

    if section != "__ended__":
        raise ValueError("missing == END ==")
    return doc


_DMS = re.compile(r"^(\d{2})([A-Za-z]{3})(\d{2})'(\d{2})\"$")

SIGN_INDEX = {s: i for i, s in enumerate(
    ["Ari", "Tau", "Gem", "Can", "Leo", "Vir",
     "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"])}


def dms_to_lon(s: str) -> float:
    m = _DMS.match(s.strip())
    if not m:
        raise ValueError(f"bad zodiacal DMS: {s!r}")
    d, sig, mi, se = m.groups()
    return SIGN_INDEX[sig] * 30.0 + int(d) + int(mi) / 60.0 + int(se) / 3600.0
