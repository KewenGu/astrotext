#!/usr/bin/env python3
"""Fetch Hipparcos (van Leeuwen 2007, VizieR I/311/hip2) astrometry for
the engine's 22 fixed stars → data/kernel/hipparcos_22.json (committed;
tiny, public ESA data, cited).  Needs network (run on the Mac).

Columns: RArad/DErad [rad, ICRS epoch J1991.25], pmRA/pmDE [mas/yr,
pmRA = μ_α*cosδ], Plx [mas].  Radial velocities are not in hip2; they
matter for space motion at the sub-0.01″/century level for these bright
stars and are set to 0 (parity gate is 0.5″).
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "kernel" / "hipparcos_22.json"

#: star name (engine key) → HIP number
HIP = {
    "Algol": 14576, "Alcyone": 17702, "Aldebaran": 21421, "Rigel": 24436,
    "Capella": 24608, "Betelgeuse": 27989, "Sirius": 32349,
    "Canopus": 30438, "Castor": 36850, "Pollux": 37826, "Procyon": 37279,
    "Alphard": 46390, "Regulus": 49669, "Denebola": 57632, "Spica": 65474,
    "Arcturus": 69673, "Antares": 80763, "Vega": 91262, "Altair": 97649,
    "Fomalhaut": 113368, "Deneb Algedi": 107556, "Achernar": 7588,
}

URL = ("https://vizier.cds.unistra.fr/viz-bin/asu-tsv?"
       + urllib.parse.urlencode({
           "-source": "I/311/hip2",
           "-out": "HIP,RArad,DErad,pmRA,pmDE,Plx",
           "-out.max": "100",
           "HIP": ",".join(str(v) for v in sorted(HIP.values())),
       }))


def main() -> None:
    with urllib.request.urlopen(URL, timeout=120) as r:
        text = r.read().decode()
    rows = {}
    for ln in text.splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        p = [x.strip() for x in ln.split("\t")]
        if len(p) >= 6:
            try:
                hip = int(p[0])
            except ValueError:
                continue
            # NOTE: despite the catalog column names RArad/DErad, VizieR's
            # asu-tsv output delivers DEGREES (verified: Canopus 95.99).
            rows[hip] = {"ra_deg": float(p[1]), "dec_deg": float(p[2]),
                         "pmra_masyr": float(p[3]), "pmde_masyr": float(p[4]),
                         "plx_mas": float(p[5])}
    missing = [n for n, h in HIP.items() if h not in rows]
    assert not missing, f"VizieR rows missing for: {missing}"
    out = {"source": "VizieR I/311/hip2 (van Leeuwen 2007), ICRS J1991.25",
           "epoch_jd_tt": 2448349.0625,   # J1991.25
           "stars": {name: {"hip": h, **rows[h]} for name, h in HIP.items()}}
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT} ({len(rows)} stars)")


if __name__ == "__main__":
    main()
