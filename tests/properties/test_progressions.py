"""M2 invariants: progression clocks, solar arc, root-finder, transits."""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "golden"))
from fixtures import ALL, build  # noqa: E402

from astrotext.core import compute_chart  # noqa: E402
from astrotext.core.angles import angdiff, norm360  # noqa: E402
from astrotext.techniques.progressions import (  # noqa: E402
    YEAR_LENGTHS, compute_progressed, compute_solar_arc, minor_jd,
    secondary_jd, solar_arc, tertiary_jd,
)
from astrotext.techniques.search import angular_roots  # noqa: E402
from astrotext.techniques.transits import compute_transits  # noqa: E402
from astrotext.timespace import Place, from_utc, resolve  # noqa: E402

UTC = dt.timezone.utc
NATAL_M = resolve(dt.datetime(1988, 6, 15, 14, 30),
                  Place(39.9042, 116.4074, "Beijing", "Asia/Shanghai"))
NATAL = compute_chart(NATAL_M)
NOW = from_utc(dt.datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
               Place(40.7128, -74.0060, "New York NY", "America/New_York"))


def test_progression_clocks_at_birth_are_identity():
    assert secondary_jd(NATAL_M, NATAL_M.jd_ut) == NATAL_M.jd_ut
    assert tertiary_jd(NATAL_M, NATAL_M.jd_ut) == NATAL_M.jd_ut
    assert minor_jd(NATAL_M, NATAL_M.jd_ut) == NATAL_M.jd_ut
    assert solar_arc(NATAL_M, NATAL_M.jd_ut) == 0.0


def test_progressed_chart_at_age_zero_equals_natal():
    rep = compute_progressed(NATAL, NATAL_M, "secondary")
    for k, p in rep.chart.points.items():
        assert abs(angdiff(p.lon, NATAL.points[k].lon)) < 1e-9, k
    assert rep.age_years == 0.0
    assert rep.angles_sa is not None
    assert abs(angdiff(rep.angles_sa.mc, NATAL.angles["MC"])) < 1e-9
    # ASC re-derived through ARMC must reproduce the natal ASC
    assert abs(angdiff(rep.angles_sa.asc, NATAL.angles["ASC"])) < 1e-6


def test_progression_clock_rates():
    one_year = NATAL_M.jd_ut + YEAR_LENGTHS["tropical"]
    assert abs(secondary_jd(NATAL_M, one_year) - (NATAL_M.jd_ut + 1.0)) < 1e-9
    assert abs(minor_jd(NATAL_M, one_year) - (NATAL_M.jd_ut + 27.321582241)) < 1e-9
    # tertiary: one month of life -> one day of ephemeris
    one_month = NATAL_M.jd_ut + 27.321582241
    assert abs(tertiary_jd(NATAL_M, one_month) - (NATAL_M.jd_ut + 1.0)) < 1e-9


def test_solar_arc_moves_every_point_by_the_same_arc():
    rep = compute_solar_arc(NATAL, NOW)
    assert 0.0 < rep.arc < 360.0
    for k, lon in rep.directed.items():
        base = NATAL.points[k].lon if k in NATAL.points else NATAL.angles[k]
        assert abs(angdiff(lon, base + rep.arc)) < 1e-9, k
    # ~age in degrees (Sun moves ~0.95-1.02 deg/day at the prog date)
    age = (NOW.jd_ut - NATAL_M.jd_ut) / YEAR_LENGTHS["tropical"]
    assert age * 0.90 < rep.arc < age * 1.05


def test_solar_arc_equals_secondary_sun_displacement():
    rep = compute_solar_arc(NATAL, NOW)
    sec = compute_progressed(NATAL, NOW, "secondary")
    sun_disp = norm360(sec.chart.points["SUN"].lon - NATAL.points["SUN"].lon)
    assert abs(angdiff(rep.arc, sun_disp)) < 1e-9


def test_angular_roots_against_engine():
    """Roots must satisfy the defining equation to sub-arcsecond level,
    verified with fresh engine calls (self-consistency at 0.2s tolerance)."""
    from astrotext.core.chart import default_ephemeris
    eph = default_ephemeris()
    target = NATAL.points["SUN"].lon
    roots = angular_roots(lambda t: eph.state(t, "SUN").lon, target,
                          NOW.jd_ut - 400, NOW.jd_ut + 400, 12.0)
    assert 2 <= len(roots) <= 3  # solar return yearly, ~800d window
    for r in roots:
        assert abs(angdiff(eph.state(r, "SUN").lon, target)) < 2e-6
    # consecutive solar returns ~365.24d apart
    for a, b in zip(roots, roots[1:]):
        assert abs((b - a) - 365.2422) < 0.03


def test_angular_roots_handles_retrograde_triple_crossing():
    from astrotext.core.chart import default_ephemeris
    eph = default_ephemeris()
    # Mercury crosses most longitudes 1 or 3 times around a retro loop.
    # natal Mercury 21.21 Gem: mid-1988 Mercury retro loop spans it.
    target = NATAL.points["MERCURY"].lon
    roots = angular_roots(lambda t: eph.state(t, "MERCURY").lon, target,
                          NATAL_M.jd_ut - 40, NATAL_M.jd_ut + 40, 6.0)
    assert len(roots) == 3  # direct, retrograde, direct again
    for r in roots:
        assert abs(angdiff(eph.state(r, "MERCURY").lon, target)) < 2e-6


def test_transits_report_consistency():
    rep = compute_transits(NATAL, NOW)
    assert rep.sky.moment is NOW
    for h in rep.hits:
        # separation/orb arithmetic
        assert abs(abs(h.separation - h.aspect.angle) - abs(h.orb_signed)) < 1e-9
        assert abs(h.orb_signed) <= rep.orb + 1e-12
        # every exact jd satisfies the aspect equation via the engine
        from astrotext.core.chart import default_ephemeris
        eph = default_ephemeris()
        for j in h.exact_jds[:2]:
            lon = eph.state(j, h.t_point).lon
            u = abs(angdiff(lon, h.n_lon))
            assert abs(u - h.aspect.angle) < 4e-6, (h.t_point, h.n_point)
    moon_hits = [h for h in rep.hits if h.t_point == "MOON"]
    for h in moon_hits:  # windowed: monthly cycle must not flood the report
        assert len(h.exact_jds) <= 8


@pytest.mark.parametrize("fx", [f for f in ALL if f.slug in
                                ("einstein", "polar", "unknown-time", "sydney")],
                         ids=lambda f: f.slug)
def test_progressions_run_on_edge_fixtures(fx):
    _, natal, _, _ = build(fx)
    rep = compute_progressed(natal, NOW, "secondary")
    assert len(rep.chart.points) == len(natal.points)
    if natal.angles is None:
        assert rep.angles_sa is None
    sa = compute_solar_arc(natal, NOW)
    assert 3.0 < sa.arc < 230.0  # all fixtures are 1856-2022 births
