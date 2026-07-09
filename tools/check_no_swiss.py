#!/usr/bin/env python3
"""K8 relicense gate — prove the default distribution carries no Swiss
Ephemeris code or data.

The Apache-2.0 relicense is conditioned (KERNEL.md §11) on the *shipped*
tree containing none of Astrodienst's AGPL material:

  * no ephemeris data files (*.se1, sefstars.txt);
  * no Swiss Ephemeris C sources (swephlib.c, swehouse.c, swecl.c, ...);
  * the default de440 backend must import and compute with `swisseph`
    absent from the environment.

The optional `backend="swiss"` *wrapper* (src/astrotext/ephem/engine.py)
is our own clean-room code that merely calls the AGPL dependency when a
developer opts in; it ships, but the dependency and its data do not.
Anything under dev/verify-only trees (vendor/, tests/cross/, and the
swetest reference harness) is excluded from the shipped set.

Exit 0 = clean (safe to relicense / release wheels); non-zero = a leak.

Run:  python tools/check_no_swiss.py        # scans the tracked tree
      python tools/check_no_swiss.py --wheel dist/astrotext-*.whl
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files/paths that are dev/verify-only and never shipped in a default wheel.
EXCLUDE_PREFIXES = (
    "vendor/",            # third-party build tree (gitignored anyway)
    ".venv/", ".git/", "_to_delete/", "dossiers/", "dossier/",
    "tests/cross/",       # swetest cross-checks (skip off the swiss profile)
)

# Data that must never appear in the default distribution.
FORBIDDEN_DATA_SUFFIXES = (".se1",)
FORBIDDEN_DATA_NAMES = {"sefstars.txt"}

# Swiss Ephemeris C translation units (identify SE source if ever vendored in).
FORBIDDEN_SOURCE_NAMES = {
    "swephlib.c", "swephlib.h", "swehouse.c", "swehouse.h", "swecl.c",
    "sweph.c", "sweph.h", "swemplan.c", "swemmoon.c", "swejpl.c",
    "swedate.c", "swehel.c", "swemptab.h", "swenut2000a.h",
}


def _tracked_files() -> list[str]:
    """Files git would ship (tracked, minus dev/verify trees).  Falls back
    to a filesystem walk when git is unavailable (e.g. sandbox mounts)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files"],
            capture_output=True, text=True, check=True).stdout
        files = [ln for ln in out.splitlines() if ln]
        if files:
            return files
    except Exception:
        pass
    files = []
    for p in ROOT.rglob("*"):
        if p.is_file():
            files.append(str(p.relative_to(ROOT)))
    return files


def _shipped(files: list[str]) -> list[str]:
    return [f for f in files
            if not any(f.startswith(pre) for pre in EXCLUDE_PREFIXES)]


def scan_tree() -> list[str]:
    problems: list[str] = []
    for f in _shipped(_tracked_files()):
        name = Path(f).name
        if name in FORBIDDEN_DATA_NAMES or f.endswith(FORBIDDEN_DATA_SUFFIXES):
            problems.append(f"SE data file in default tree: {f}")
        if name in FORBIDDEN_SOURCE_NAMES:
            problems.append(f"SE C source in default tree: {f}")
    return problems


def scan_wheel(whl: Path) -> list[str]:
    problems: list[str] = []
    with zipfile.ZipFile(whl) as z:
        for n in z.namelist():
            base = n.rsplit("/", 1)[-1]
            if base in FORBIDDEN_DATA_NAMES or n.endswith(FORBIDDEN_DATA_SUFFIXES):
                problems.append(f"SE data file in wheel: {n}")
            if base in FORBIDDEN_SOURCE_NAMES:
                problems.append(f"SE C source in wheel: {n}")
    return problems


def check_default_backend_runs_without_swisseph() -> list[str]:
    """The de440 default must compute with `swisseph` unimportable."""
    code = (
        "import sys, builtins\n"
        "_real = builtins.__import__\n"
        "def _blocked(name, *a, **k):\n"
        "    if name == 'swisseph' or name.startswith('swisseph.'):\n"
        "        raise ImportError('swisseph blocked by check_no_swiss')\n"
        "    return _real(name, *a, **k)\n"
        "builtins.__import__ = _blocked\n"
        "from astrotext.ephem import Ephemeris\n"
        "e = Ephemeris()\n"
        "assert e.backend == 'de440', e.backend\n"
        "s = e.state(2451545.0, 'SUN')\n"
        "assert 279.0 < s.lon < 281.0, s.lon\n"   # Sun ~280.4° at J2000
        "print('OK', round(s.lon, 4))\n"
    )
    env_src = str(ROOT / "src")
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True,
                       env={**_env(), "PYTHONPATH": env_src})
    if r.returncode != 0:
        return [f"de440 backend failed without swisseph:\n{r.stderr.strip()}"]
    return []


def _env() -> dict:
    import os
    e = dict(os.environ)
    e.setdefault("SE_EPHE_PATH", str(ROOT / "data" / "ephe"))
    return e


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wheel", type=Path, help="also scan a built wheel")
    ap.add_argument("--skip-runtime", action="store_true",
                    help="skip the de440-without-swisseph import check")
    args = ap.parse_args()

    problems = scan_tree()
    if args.wheel:
        problems += scan_wheel(args.wheel)
    if not args.skip_runtime:
        problems += check_default_backend_runs_without_swisseph()

    if problems:
        print("FAIL — Swiss Ephemeris material found in the default distribution:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("PASS — default distribution is Swiss-Ephemeris-free "
          "(no .se1 / sefstars / SE C sources; de440 computes without swisseph).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
