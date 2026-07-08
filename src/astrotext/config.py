"""Repository-level paths and environment resolution.

Everything is overridable via environment variables so the package also works
when moved out of the repository:
  SE_EPHE_PATH   directory with Swiss Ephemeris data files (sepl/semo/seas .se1)
  SWETEST_BIN    path to the compiled swetest reference CLI (verify layer only)
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def ephe_path() -> Path:
    return Path(os.environ.get("SE_EPHE_PATH", REPO_ROOT / "data" / "ephe"))


def swetest_bin() -> Path:
    return Path(os.environ.get("SWETEST_BIN", REPO_ROOT / "vendor" / "lib" / "swetest"))


#: Ephemeris data files currently vendored (SE 2.10.03). Range they cover:
EPHE_RANGE_YEARS = (1800, 2399)
