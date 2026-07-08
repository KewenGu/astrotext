"""M2 snapshot regression for transits/progressions/solar-arc renders."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from fixtures import ALL, TIMED_SLUGS, build_timed  # noqa: E402

SNAP_DIR = Path(__file__).parent / "snapshots"
FIXTURES = [f for f in ALL if f.slug in TIMED_SLUGS]


@pytest.mark.parametrize("fx", FIXTURES, ids=[f.slug for f in FIXTURES])
def test_timed_snapshots(fx):
    reports = build_timed(fx)
    for name, text in reports.items():
        snap = SNAP_DIR / f"{fx.slug}--{name}.txt"
        assert snap.exists(), f"missing {snap.name}; run tools/regen_snapshots.py"
        assert text == snap.read_text(encoding="utf-8"), (fx.slug, name)
        assert text.endswith("== END ==\n")
