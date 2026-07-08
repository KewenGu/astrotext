#!/usr/bin/env python3
"""Thin entry point for `make verify` — see astrotext.verify.report."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "vendor" / "py", ROOT / "vendor" / "lib"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from astrotext.verify.report import main  # noqa: E402

sys.exit(main())
