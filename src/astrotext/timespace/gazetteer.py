"""Offline gazetteer: place name (incl. Chinese aliases) -> lat/lon + IANA tz.

Data: a compact TSV compiled from GeoNames cities1000 + admin1 + country
tables by tools/build_gazetteer.py into data/gazetteer/cities.tsv.gz
(provenance and license: CC-BY, geonames.org — see data/gazetteer/README).

Columns: name, asciiname, alternatenames('|'-separated), lat, lon,
country_code, country_name, admin1, population, timezone.

Matching (deterministic, no fuzzy magic):
  1. curated zh-exonym supplement (纽约/罗马/河内... — checked first, see
     zh_exonyms.py for why it must precede the alternate index);
  2. case-insensitive exact match on name / asciiname (eager index);
  3. on miss, case-insensitive exact match on alternate names (lazy index —
     this is where 北京 / 上海 / नई दिल्ली resolve);
  4. CJK admin-suffix normalization: GeoNames often stores 江阴市 while
     users type 江阴 — on a CJK miss we retry with 市/县/区/镇 appended
     (and stripped, for the reverse case), in that fixed order;
  5. ranking: population descending; a runner-up with >= 1/10 of the top
     population triggers an ambiguity flag listing the top candidates
     (pass country='CN' etc. to disambiguate).
Misses raise with guidance (pinyin/English names also work: 'Jiangyin').
"""
from __future__ import annotations

import gzip
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .. import config
from .place import Place

__all__ = ["GazetteerHit", "GazetteerUnavailable", "PlaceNotFound",
           "lookup", "resolve_place", "data_path", "available"]


class GazetteerUnavailable(RuntimeError):
    """The compiled data file is missing (run tools/build_gazetteer.py)."""


class PlaceNotFound(ValueError):
    """No entry matches the query."""


@dataclass(frozen=True, slots=True)
class GazetteerHit:
    name: str
    ascii: str
    lat: float
    lon: float
    tz: str
    country: str
    admin1: str
    population: int
    matched_on: str          # 'name' | 'ascii' | 'alternate'

    def label(self) -> str:
        adm = f", {self.admin1}" if self.admin1 else ""
        return f"{self.name}{adm}, {self.country}"


def data_path() -> Path:
    return Path(os.environ.get(
        "ASTROTEXT_GAZETTEER",
        config.REPO_ROOT / "data" / "gazetteer" / "cities.tsv.gz"))


def available() -> bool:
    return data_path().exists()


class _Gazetteer:
    def __init__(self, path: Path):
        if not path.exists():
            raise GazetteerUnavailable(
                f"gazetteer data not found at {path}; build it with "
                f"tools/build_gazetteer.py (needs GeoNames cities1000) or "
                f"pass lat/lon/tz directly")
        self.rows: list[tuple] = []
        primary: dict[str, list[int]] = {}
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as f:
            for i, line in enumerate(f):
                p = line.rstrip("\n").split("\t")
                if len(p) != 10:
                    continue
                row = (p[0], p[1], p[2], float(p[3]), float(p[4]),
                       p[5], p[6], p[7], int(p[8] or 0), p[9])
                self.rows.append(row)
                for key in {p[0].lower(), p[1].lower()}:
                    if key:
                        primary.setdefault(key, []).append(i)
        self.primary = primary
        self._alt: dict[str, list[int]] | None = None

    def alt_index(self) -> dict[str, list[int]]:
        if self._alt is None:
            alt: dict[str, list[int]] = {}
            for i, row in enumerate(self.rows):
                for a in row[2].split("|"):
                    a = a.strip().lower()
                    if a and len(a) <= 60:
                        alt.setdefault(a, []).append(i)
            self._alt = alt
        return self._alt

    def find(self, query: str) -> tuple[list[int], str]:
        q = query.strip().lower()
        if q in self.primary:
            return self.primary[q], "name"
        alt = self.alt_index()
        if q in alt:
            return alt[q], "alternate"
        return [], "none"

    def find_staged(self, query: str) -> list[tuple[list[int], str]]:
        """Primary stage, then alternate stage — callers apply their filters
        per stage and fall through when a stage filters down to nothing
        (e.g. towns literally NAMED 'Cologne' exist in IT/US; a country=DE
        query must fall through to Koeln's alternate names)."""
        q = query.strip().lower()
        stages: list[tuple[list[int], str]] = []
        if q in self.primary:
            stages.append((self.primary[q], "name"))
        alt = self.alt_index()
        if q in alt:
            stages.append((alt[q], "alternate"))
        return stages


@lru_cache(maxsize=1)
def _load() -> _Gazetteer:
    return _Gazetteer(data_path())


_CJK_SUFFIXES = ("市", "县", "区", "镇")


def _has_cjk(s: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def lookup(query: str, country: str | None = None, limit: int = 5
           ) -> list[GazetteerHit]:
    """Ranked matches (population desc). ``country`` is an ISO-2 code or
    a country name as compiled into the data."""
    gz = _load()
    # Curated zh-exonym supplement FIRST (name mapping only; coords stay
    # gazetteer-sourced).  It must precede the alternate-name index because
    # GeoNames alternates collide: 河内 tags a Japanese hamlet (Kochi), 罗马
    # tags Roma/Lesotho — while the intended megacities lack the zh name.
    from .zh_exonyms import ZH_EXONYMS
    mapped = ZH_EXONYMS.get(query.strip())
    if mapped:
        mq, mc = mapped
        stages = gz.find_staged(mq)
        label = "zh-exonym-supplement"
        if country is None:
            country = mc
    else:
        stages = gz.find_staged(query)
        label = None

    def collect(stage_list, matched_label: str | None, q: str) -> list[GazetteerHit]:
        for idxs, how in stage_list:
            hits = []
            for i in idxs:
                n, a, _alts, lat, lon, code, ctry, adm1, pop, tz = gz.rows[i]
                if country and country.lower() not in (code.lower(), ctry.lower()):
                    continue
                if matched_label:
                    matched = matched_label
                elif how == "name" and n.lower() != q.strip().lower():
                    matched = "ascii"
                else:
                    matched = how
                hits.append(GazetteerHit(n, a, lat, lon, tz, ctry, adm1, pop, matched))
            if hits:
                hits.sort(key=lambda h: (-h.population, h.country, h.name))
                return hits[:limit]
        return []

    hits = collect(stages, label, query)
    if hits or not _has_cjk(query):
        return hits

    # CJK admin-suffix normalization: try 江阴 -> 江阴市/县/区/镇, and the
    # stripped form for suffixed input whose row only carries the bare name.
    q = query.strip()
    variants = [(q + suf, f"alternate(zh-suffix:+{suf})") for suf in _CJK_SUFFIXES]
    if len(q) > 2 and q.endswith(_CJK_SUFFIXES):
        variants.append((q[:-1], f"alternate(zh-suffix:-{q[-1]})"))
    for vq, vlabel in variants:
        hits = collect(gz.find_staged(vq), vlabel, vq)
        if hits:
            return hits
    return []


def resolve_place(query: str, country: str | None = None
                  ) -> tuple[Place, tuple[str, ...]]:
    """Top match as a Place (+ deterministic warning flags).

    Ambiguity flag when the runner-up has >= 1/10 the top population."""
    hits = lookup(query, country)
    if not hits:
        raise PlaceNotFound(
            f"no gazetteer entry for {query!r}"
            + (f" in {country}" if country else "")
            + "; check spelling, add country=, try the pinyin/English name "
              "(e.g. 'Jiangyin'), or pass lat/lon/tz directly")
    top = hits[0]
    flags: list[str] = [f"place-resolved:{query!r} -> {top.label()} "
                        f"({top.lat:.4f},{top.lon:.4f} tz={top.tz} "
                        f"pop={top.population}) matched-on={top.matched_on}"]
    rivals = [h for h in hits[1:] if h.population * 10 >= top.population]
    if rivals:
        alts = "; ".join(f"{h.label()} pop={h.population}" for h in rivals[:3])
        flags.append(f"place-ambiguous:also matches {alts} — pass country= "
                     f"or lat/lon to override")
    place = Place(lat=top.lat, lon=top.lon, name=top.label(), tz=top.tz)
    return place, tuple(flags)
