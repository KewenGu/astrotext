"""Driver for the swetest reference CLI (compiled from Astrodienst's official
sources by tools/vendor.sh).

swetest is the ground truth for the whole project: it is the same C library
underneath, but reached through a completely independent path (command line,
its own argument parsing, its own time handling).  Bit-level agreement between
our Python wrapper and swetest proves the wrapper adds zero error.
"""
from __future__ import annotations

import re
import subprocess
from functools import lru_cache

from .. import config

#: swetest -p letters for the points we verify, and the names it prints
LETTERS = "0123456789mtAD"
NAME_TO_KEY = {
    "Sun": "SUN", "Moon": "MOON", "Mercury": "MERCURY", "Venus": "VENUS",
    "Mars": "MARS", "Jupiter": "JUPITER", "Saturn": "SATURN",
    "Uranus": "URANUS", "Neptune": "NEPTUNE", "Pluto": "PLUTO",
    "mean Node": "MEAN_NODE", "true Node": "TRUE_NODE",
    "mean Apogee": "MEAN_APOGEE", "Chiron": "CHIRON",
}

_NUM = re.compile(r"-?\d+\.\d+")


def _run(args: list[str]) -> str:
    cmd = [str(config.swetest_bin()), f"-edir{config.ephe_path()}", *args]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(f"swetest failed: {' '.join(cmd)}\n{out.stderr or out.stdout}")
    return out.stdout


def _parse_line(line: str) -> tuple[str, list[float]] | None:
    m = _NUM.search(line)
    if not m:
        return None
    name = line[: m.start()].strip()
    nums = [float(x) for x in _NUM.findall(line)]
    return name, nums


@lru_cache(maxsize=4096)
def positions(jd_ut: float, letters: str = LETTERS) -> dict[str, tuple[float, float, float]]:
    """Reference (lon, lat, lon_speed) per point key at a UT Julian day.

    Format string ``Plbs``: name, longitude (decimal), latitude (decimal),
    daily longitude speed (decimal).  Distance is excluded on purpose — the
    Moon's is printed in nonstandard units and it is astrologically inert.
    """
    # repr() = shortest round-trip float, so swetest's atof reconstructs the
    # IDENTICAL double; %.9f truncation costs up to 2e-7 deg on the fast MC.
    out = _run([f"-bj{jd_ut!r}", "-ut", f"-p{letters}", "-fPlbs", "-head"])
    res: dict[str, tuple[float, float, float]] = {}
    for line in out.splitlines():
        parsed = _parse_line(line)
        if not parsed:
            continue
        name, nums = parsed
        if name in NAME_TO_KEY and len(nums) >= 3:
            res[NAME_TO_KEY[name]] = (nums[0], nums[1], nums[2])
    missing = set(NAME_TO_KEY.values()) - set(res)
    if letters == LETTERS and missing:
        raise RuntimeError(f"swetest output missing points {missing}:\n{out}")
    return res


@lru_cache(maxsize=1024)
def houses(jd_ut: float, lon: float, lat: float, hsys: str = "P"
           ) -> tuple[tuple[float, ...], dict[str, float]]:
    """Reference house cusps 1..12 and angles."""
    out = _run([f"-bj{jd_ut!r}", "-ut", "-p", f"-house{lon},{lat},{hsys}", "-fPl", "-head"])
    cusps: dict[int, float] = {}
    named: dict[str, float] = {}
    for line in out.splitlines():
        parsed = _parse_line(line)
        if not parsed:
            continue
        name, nums = parsed
        if not nums:
            continue
        m = re.match(r"^house\s+(\d+)$", name)
        if m:
            cusps[int(m.group(1))] = nums[0]
        elif name == "Ascendant":
            named["ASC"] = nums[0]
        elif name == "MC":
            named["MC"] = nums[0]
        elif name == "ARMC":
            named["ARMC"] = nums[0]
        elif name == "Vertex":
            named["VERTEX"] = nums[0]
    if len(cusps) != 12:
        raise RuntimeError(f"swetest houses parse failed:\n{out}")
    return tuple(cusps[i] for i in range(1, 13)), named


def version() -> str:
    out = _run(["-b1.1.2000", "-ut12:00:00", "-p0", "-fP"])
    m = re.search(r"Swiss Ephemeris version ([\d.]+)", out)
    return m.group(1) if m else "unknown"
