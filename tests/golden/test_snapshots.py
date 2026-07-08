"""Snapshot regression: rendered output of every golden fixture is frozen.

Regenerate intentionally with:  python tools/regen_snapshots.py
Any diff = a behavior change that must be explained in the commit.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from fixtures import ALL, build  # noqa: E402

from astrotext.render import parse, render_chart  # noqa: E402

SNAP_DIR = Path(__file__).parent / "snapshots"


def _render(fx) -> str:
    m, c, hour, stars = build(fx)
    return render_chart(c, fx.name, hour, stars)


@pytest.mark.parametrize("fx", ALL, ids=[f.slug for f in ALL])
def test_snapshot(fx):
    snap = SNAP_DIR / f"{fx.slug}.txt"
    assert snap.exists(), f"missing snapshot {snap.name}; run tools/regen_snapshots.py"
    assert _render(fx) == snap.read_text(encoding="utf-8"), (
        f"rendered output changed for {fx.slug}; if intentional, regenerate "
        f"snapshots and explain in the commit message")


@pytest.mark.parametrize("fx", ALL, ids=[f.slug for f in ALL])
def test_render_deterministic(fx):
    assert _render(fx) == _render(fx)


@pytest.mark.parametrize("fx", ALL, ids=[f.slug for f in ALL])
def test_roundtrip_parse(fx):
    """Every number in the text must reproduce the chart's value at printed
    precision — the text IS the database, so it must be faithful."""
    m, c, hour, stars = build(fx)
    doc = parse(render_chart(c, fx.name, hour, stars))

    pts = {row[0]: row for row in doc["sections"]["POINTS"]}
    assert list(pts) == [k for k in c.settings.points if k in c.points]
    from astrotext.render.parse import dms_to_lon
    for k, row in pts.items():
        p = c.points[k]
        assert abs(float(row[3]) - p.lon) < 5e-7, (k, "lon")
        assert abs(float(row[4]) - p.lat) < 5e-7
        assert abs(float(row[5]) - p.lon_speed) < 5e-7
        assert abs(float(row[6]) - p.dec) < 5e-5
        assert abs(dms_to_lon(row[1]) - p.lon) <= 0.5 / 3600 + 1e-9, (k, "dms")
        assert (row[2] == "-") == (p.house is None)
        assert ("R" in row[7]) == p.retrograde
        assert ("OOB" in row[7]) == p.oob

    if c.angles is not None:
        ang = {row[0]: row for row in doc["sections"]["ANGLES"]}
        for a in ("ASC", "MC", "DSC", "IC", "VERTEX", "ARMC"):
            assert abs(float(ang[a][2]) - c.angles[a]) < 5e-7
    if c.cusps is not None:
        hs = [r for r in doc["sections"][f"HOUSES ({c.house_system_used})"]]
        assert len(hs) == 12
        for i, row in enumerate(hs):
            assert abs(float(row[2]) - c.cusps[i]) < 5e-7

    asp_rows = doc["sections"].get("ASPECTS", [])
    assert len(asp_rows) == len(c.aspects)
    for row, hit in zip(asp_rows, c.aspects):
        assert row[0] == hit.p1 and row[2] == hit.p2
        assert abs(float(row[3]) - hit.orb_signed) < 5e-4
        assert row[4] == hit.phase

    # warnings round-trip
    assert doc["warnings"] == list(c.flags)
