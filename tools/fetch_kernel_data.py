#!/usr/bin/env python3
"""Fetch kernel-v2 data files (not committed) with pinned SHA-256.

Downloads the DE440 excerpt via jplephem's ranged-GET excerpt tool
(~65 MB transferred out of the 114 MB full file).  Needs network +
jplephem installed; run from any machine, files land in data/kernel/.

    python tools/fetch_kernel_data.py

K3 will add the Chiron SPK (JPL Horizons) here.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "kernel"

DE440_URL = ("https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"
             "spk/planets/de440.bsp")
DE440_EXCERPT = DEST / "de440_1799_2400.bsp"
# python -m jplephem excerpt 1799/1/1 2400/2/1 <url> <out>, jplephem 2.24:
DE440_SHA256 = "5aadad33862e235633f72a0e64c6e56d333e22c38602efad143cca801daa06f9"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    if not DE440_EXCERPT.exists():
        print(f"fetching DE440 excerpt 1799-2400 from {DE440_URL} ...")
        subprocess.run(
            [sys.executable, "-m", "jplephem", "excerpt",
             "1799/1/1", "2400/2/1", DE440_URL, str(DE440_EXCERPT)],
            check=True)
    got = sha256(DE440_EXCERPT)
    if got != DE440_SHA256:
        raise SystemExit(
            f"SHA-256 mismatch for {DE440_EXCERPT}:\n  got  {got}\n"
            f"  want {DE440_SHA256}\n(delete the file and re-fetch, or "
            f"update the pin if jplephem's excerpt format changed)")
    print(f"ok  {DE440_EXCERPT.name}  sha256={got[:16]}…")


if __name__ == "__main__":
    main()
