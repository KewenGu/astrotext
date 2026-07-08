#!/usr/bin/env python3
"""Compile GeoNames dumps into data/gazetteer/cities.tsv.gz.

Inputs (download from https://download.geonames.org/export/dump/):
  cities1000.zip (or cities500/cities15000)   the city table
  admin1CodesASCII.txt                        province/state names
  countryInfo.txt                             country names

Usage:
  python3 tools/build_gazetteer.py cities1000.zip admin1CodesASCII.txt countryInfo.txt

Output columns (10, tab-separated, gz):
  name  asciiname  alternatenames('|')  lat  lon  country_code
  country_name  admin1_name  population  timezone

License note: GeoNames data is CC-BY 4.0 — attribution kept in
data/gazetteer/README.
"""
from __future__ import annotations

import gzip
import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "gazetteer" / "cities.tsv.gz"


def load_admin1(path: Path) -> dict[str, str]:
    m: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        p = line.split("\t")
        if len(p) >= 2:
            m[p[0]] = p[1]          # "CN.22" -> "Beijing"
    return m


def load_countries(path: Path) -> dict[str, str]:
    m: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("#"):
            continue
        p = line.split("\t")
        if len(p) >= 5:
            m[p[0]] = p[4]          # "CN" -> "China"
    return m


def city_lines(path: Path):
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            inner = next(n for n in z.namelist() if n.endswith(".txt"))
            with z.open(inner) as f:
                yield from io.TextIOWrapper(f, encoding="utf-8")
    else:
        with open(path, encoding="utf-8") as f:
            yield from f


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    cities, admin1_p, country_p = (Path(a) for a in argv)
    admin1 = load_admin1(admin1_p)
    countries = load_countries(country_p)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with gzip.open(OUT, "wt", encoding="utf-8", compresslevel=9) as out:
        for line in city_lines(cities):
            p = line.rstrip("\n").split("\t")
            if len(p) < 18:
                continue
            # geonames columns: 1 name, 2 ascii, 3 alternates, 4 lat, 5 lon,
            # 8 country, 10 admin1, 14 population, 17 timezone
            name, ascii_, alts = p[1], p[2], p[3]
            lat, lon = p[4], p[5]
            ctry_code, adm1_code = p[8], p[10]
            pop, tz = p[14], p[17]
            if not tz:
                continue
            ctry = countries.get(ctry_code, ctry_code)
            adm1 = admin1.get(f"{ctry_code}.{adm1_code}", "")
            seen = {name.lower(), ascii_.lower()}
            alts_list = []
            for a in alts.split(","):
                a = a.strip()
                if a and len(a) <= 60 and a.lower() not in seen:
                    seen.add(a.lower())
                    alts_list.append(a)
            alts_clean = "|".join(alts_list)
            out.write("\t".join([name, ascii_, alts_clean, lat, lon,
                                 ctry_code, ctry, adm1, pop or "0", tz]) + "\n")
            n += 1
    size = OUT.stat().st_size / 1e6
    print(f"wrote {n} places -> {OUT} ({size:.1f} MB)")

    readme = OUT.parent / "README"
    readme.write_text(
        "Compiled from GeoNames (https://www.geonames.org), license CC-BY 4.0.\n"
        "Source dumps: cities1000, admin1CodesASCII, countryInfo.\n"
        "Rebuild: python3 tools/build_gazetteer.py <cities.zip> <admin1> <country>\n",
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
