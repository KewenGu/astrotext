"""Chart-level invariants across all golden fixtures + random moments.

These are the "mathematics of the technique" — they hold for EVERY chart, so
we test them in bulk rather than case by case.
"""
import datetime as dt
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "golden"))
from fixtures import ALL, build  # noqa: E402

from astrotext.core import MODERN, compute_chart  # noqa: E402
from astrotext.core.angles import angdiff, norm360  # noqa: E402
from astrotext.core.chart import _house_of  # noqa: E402
from astrotext.core.dignities import (  # noqa: E402
    BOUNDS_EGYPTIAN, DECANS_CHALDEAN, DOMICILE, EXALTATION, TRIPLICITY,
)
from astrotext.timespace import Place, resolve  # noqa: E402

CHARTS = [(fx, *build(fx)) for fx in ALL]
IDS = [fx.slug for fx in ALL]


@pytest.mark.parametrize("fx,m,c,hour,stars", CHARTS, ids=IDS)
def test_points_well_formed(fx, m, c, hour, stars):
    for k, p in c.points.items():
        assert 0.0 <= p.lon < 360.0
        assert 0 <= p.sign <= 11
        assert 0.0 <= p.sign_deg < 30.0
        assert abs(30 * p.sign + p.sign_deg - p.lon) < 1e-9
        assert p.retrograde == (p.lon_speed < 0)
        assert p.oob == (abs(p.dec) > c.obliquity)
        if c.cusps is None:
            assert p.house is None
        else:
            assert 1 <= p.house <= 12


@pytest.mark.parametrize("fx,m,c,hour,stars", CHARTS, ids=IDS)
def test_house_geometry(fx, m, c, hour, stars):
    if c.cusps is None:
        return
    # each cusp lies in its own house; total arc = 360
    total = sum(norm360(c.cusps[(i + 1) % 12] - c.cusps[i]) for i in range(12))
    assert abs(total - 360.0) < 1e-6
    for i in range(12):
        assert _house_of(c.cusps[i] + 1e-7, c.cusps) == i + 1
    # quadrant systems anchor ASC/MC to cusps 1/10
    if c.house_system_used in ("P", "K", "O", "R", "C", "B"):
        assert abs(angdiff(c.angles["ASC"], c.cusps[0])) < 1e-6
        assert abs(angdiff(c.angles["MC"], c.cusps[9])) < 1e-6
    assert abs(angdiff(c.angles["DSC"], c.angles["ASC"] + 180)) < 1e-9
    assert abs(angdiff(c.angles["IC"], c.angles["MC"] + 180)) < 1e-9


@pytest.mark.parametrize("fx,m,c,hour,stars", CHARTS, ids=IDS)
def test_south_node_mirrors_north(fx, m, c, hour, stars):
    if "TRUE_NODE" in c.points and "SOUTH_NODE_TRUE" in c.points:
        n, s = c.points["TRUE_NODE"], c.points["SOUTH_NODE_TRUE"]
        assert abs(angdiff(s.lon, n.lon + 180)) < 1e-9
        assert abs(s.dec + n.dec) < 1e-9
        assert s.lon_speed == n.lon_speed


@pytest.mark.parametrize("fx,m,c,hour,stars", CHARTS, ids=IDS)
def test_aspects_valid(fx, m, c, hour, stars):
    keys = set(c.points) | set(c.settings.angle_points)
    seen = set()
    for h in c.aspects:
        assert h.p1 in keys and h.p2 in keys and h.p1 != h.p2
        assert (h.p1, h.p2, h.aspect.key) not in seen
        seen.add((h.p1, h.p2, h.aspect.key))
        assert 0.0 <= h.separation <= 180.0
        assert h.orb_abs <= h.orb_allowed + 1e-12
        assert abs(abs(h.separation - h.aspect.angle) - h.orb_abs) < 1e-12
        assert h.phase in ("A", "S", "E", "-")
        # angles have no speed => never A/S when either side is an angle
        if h.p1 in c.settings.angle_points or h.p2 in c.settings.angle_points:
            assert h.phase in ("E", "-")


@pytest.mark.parametrize("fx,m,c,hour,stars", CHARTS, ids=IDS)
def test_lots_formulas(fx, m, c, hour, stars):
    if not c.lots:
        return
    asc = c.angles["ASC"]
    s, mo = c.points["SUN"].lon, c.points["MOON"].lon
    if c.is_day:
        assert abs(angdiff(c.lots["FORTUNE"], asc + mo - s)) < 1e-9
        assert abs(angdiff(c.lots["SPIRIT"], asc + s - mo)) < 1e-9
    else:
        assert abs(angdiff(c.lots["FORTUNE"], asc + s - mo)) < 1e-9
        assert abs(angdiff(c.lots["SPIRIT"], asc + mo - s)) < 1e-9
    # Fortune and Spirit mirror each other across the ASC
    assert abs(angdiff(c.lots["FORTUNE"], asc) + angdiff(c.lots["SPIRIT"], asc)) < 1e-9


@pytest.mark.parametrize("fx,m,c,hour,stars", CHARTS, ids=IDS)
def test_sect_and_hour_consistency(fx, m, c, hour, stars):
    if c.is_day is not None and c.sun_altitude is not None and abs(c.sun_altitude) > 1.0:
        # away from the horizon the ecliptic-axis sect must match true altitude
        if not any(f.startswith("sect-convention-note") for f in c.flags):
            assert c.is_day == (c.sun_altitude > 0)
    if hour is not None and not hour.polar:
        assert hour.sunrise_jd <= m.jd_ut < hour.next_sunrise_jd
        assert 1 <= hour.hour_no <= 24
        assert hour.is_day_hour == (m.jd_ut < hour.sunset_jd)
        if hour.hour_no == 1:
            assert hour.hour_ruler == hour.day_ruler


def test_dignity_tables_structure():
    # bounds: each sign sums to 30 and uses the 5 non-luminaries exactly once
    for sign, bounds in enumerate(BOUNDS_EGYPTIAN):
        assert bounds[-1][0] == 30, sign
        spans, planets, prev = [], [], 0
        for limit, planet in bounds:
            assert limit > prev
            spans.append(limit - prev)
            planets.append(planet)
            prev = limit
        assert sum(spans) == 30, sign
        assert sorted(planets) == sorted(
            ["MERCURY", "VENUS", "MARS", "JUPITER", "SATURN"]), sign
    # decans: chaldean sequence is period-7 across the 36 faces
    flat = [DECANS_CHALDEAN[i][j] for i in range(12) for j in range(3)]
    for a, b in zip(flat, flat[7:]):
        assert a == b
    assert flat[0] == "MARS"  # Aries I
    # domicile symmetry: each non-luminary rules exactly two signs, luminaries one
    from collections import Counter
    cnt = Counter(DOMICILE)
    assert cnt["SUN"] == cnt["MOON"] == 1
    for p in ("MERCURY", "VENUS", "MARS", "JUPITER", "SATURN"):
        assert cnt[p] == 2
    # exaltation signs are all distinct
    ex_signs = [s for s, _ in EXALTATION.values()]
    assert len(set(ex_signs)) == len(ex_signs)
    # triplicity: day/night/participating are distinct planets per element
    for rulers in TRIPLICITY.values():
        assert len(set(rulers)) == 3


def test_unknown_time_suppressions():
    fx = next(f for f in ALL if f.slug == "unknown-time")
    _, c, hour, _ = build(fx)
    assert c.cusps is None and c.angles is None
    assert c.lots == {}
    assert hour is None
    assert all(h.p1 not in ("ASC", "MC") and h.p2 not in ("ASC", "MC")
               for h in c.aspects)
    assert any(f.startswith("unknown-birth-time") for f in c.flags)
    assert any(f.startswith("dignities-assume-day") for f in c.flags)


def test_polar_fallback_flagged():
    fx = next(f for f in ALL if f.slug == "polar")
    _, c, hour, _ = build(fx)
    assert c.house_system_used == "O"
    assert any(f.startswith("polar-fallback:P->O") for f in c.flags)
    assert hour is not None and hour.polar  # December on Svalbard: no sunrise


def test_random_charts_do_not_crash():
    rng = random.Random(4242)
    for _ in range(25):
        year = rng.randint(1800, 2390)
        local = dt.datetime(year, rng.randint(1, 12), rng.randint(1, 28),
                            rng.randint(0, 23), rng.randint(0, 59))
        lat = rng.uniform(-89.0, 89.0)
        lon = rng.uniform(-180.0, 180.0)
        m = resolve(local, Place(lat, lon, tz="UTC+0"))
        c = compute_chart(m, MODERN)
        assert len(c.points) == len(MODERN.points)
        assert c.moon.phase
