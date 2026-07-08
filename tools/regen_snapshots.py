#!/usr/bin/env python3
"""Regenerate golden snapshots (intentional behavior changes only)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "vendor" / "py", ROOT / "vendor" / "lib",
          ROOT / "tests" / "golden"):
    sys.path.insert(0, str(p))
import os  # noqa: E402
os.environ.setdefault("SE_EPHE_PATH", str(ROOT / "data" / "ephe"))

from fixtures import ALL, build  # noqa: E402
from astrotext.render import render_chart  # noqa: E402

snap_dir = ROOT / "tests" / "golden" / "snapshots"
snap_dir.mkdir(exist_ok=True)
for fx in ALL:
    m, c, hour, stars = build(fx)
    text = render_chart(c, fx.name, hour, stars)
    (snap_dir / f"{fx.slug}.txt").write_text(text, encoding="utf-8")
    print(f"{fx.slug:24s} {len(text.splitlines()):4d} lines  flags={len(c.flags)}")
print(f"\n{len(ALL)} snapshots -> {snap_dir}")
