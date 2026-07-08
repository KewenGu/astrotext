"""M3 invariants: returns, firdaria, profections, VOC."""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "golden"))

from astrotext.core import compute_chart  # noqa: E402
from astrotext.core.angles import angdiff  # noqa: E402
from astrotext.core.dignities import DOMICILE  # noqa: E402
from astrotext.core.zodiac import sign_index  # noqa: E402
from astrotext.techniques.firdaria import MAJOR_YEARS, PLANET_ORDER, firdaria  # noqa: E402
from astrotext.techniques.profections import profections  # noqa: E402
from astrotext.techniques.returns import compute_return  # noqa: E402
from astrotext.techniques.transits import compute_moon_void  # noqa: E402
from astrotext.timespace import Place, from_utc, resolve  # noqa: E402

UTC = dt.timezone.utc
NATAL_M = resolve(dt.datetime(1988, 6, 15, 14, 30),
                  Place(39.9042, 116.4074, "Beijing", "Asia/Shanghai"))
NATAL = compute_chart(NATAL_M)
NIGHT_M = resolve(dt.datetime(1988, 6, 15, 2, 30),
                  Place(39.9042, 116.4074, "Beijing", "Asia/Shanghai"))
NIGHT = compute_chart(NIGHT_M)
NOW = from_utc(dt.datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
               Place(40.7128, -74.0060, "New York NY", "America/New_York"))


# ---- returns ---------------------------------------------------------------

def test_solar_return_brackets_target_and_is_exact():
    sr = compute_return(NATAL, NOW, "SUN")
    assert sr.active_jd <= NOW.jd_ut < sr.next_jd
    assert sr.residual_deg < 2e-6
    assert abs((sr.next_jd - sr.active_jd) - 365.2422) < 0.03
    # the return chart's Sun stands on the natal Sun
    assert abs(angdiff(sr.chart.points["SUN"].lon, NATAL.points["SUN"].lon)) < 2e-6
    # cast at the current location by default
    assert sr.chart.moment.place.name == "New York NY"


def test_lunar_return_monthly_cycle():
    lr = compute_return(NATAL, NOW, "MOON")
    assert lr.active_jd <= NOW.jd_ut < lr.next_jd
    assert abs((lr.next_jd - lr.active_jd) - 27.3217) < 0.35
    # Moon moves ~13.8 deg/day; 0.05s time precision => up to ~9e-6 deg residual
    assert lr.residual_deg < 1e-5


def test_precessed_return_shifts_by_accumulated_precession():
    sr = compute_return(NATAL, NOW, "SUN")
    srp = compute_return(NATAL, NOW, "SUN", precessed=True)
    age = (NOW.jd_ut - NATAL_M.jd_ut) / 365.2422
    expected_days = age * (50.29 / 3600.0) / 0.9856  # deg / (deg/day)
    diff = srp.active_jd - sr.active_jd
    assert abs(abs(diff) - expected_days) < 0.06
    assert srp.residual_deg < 2e-6


def test_return_at_birthplace_option():
    sr = compute_return(NATAL, NOW, "SUN", place=NATAL_M.place)
    assert sr.chart.moment.place.name == "Beijing"
    sr2 = compute_return(NATAL, NOW, "SUN")
    assert abs(sr.active_jd - sr2.active_jd) < 1e-9  # timing is location-free


# ---- firdaria ----------------------------------------------------------------

def _majors(periods):
    return [p for p in periods if p.level == 1]


def test_firdaria_structure_day():
    f = firdaria(NATAL, cycles=1)
    majors = _majors(f)
    assert [p.lord for p in majors] == [
        "SUN", "VENUS", "MERCURY", "MOON", "SATURN", "JUPITER", "MARS",
        "NORTH_NODE", "SOUTH_NODE"]
    assert majors[0].start_age == 0.0 and majors[-1].end_age == 75.0
    for a, b in zip(majors, majors[1:]):
        assert abs(a.end_jd - b.start_jd) < 1e-9  # gapless
    subs = [p for p in f if p.level == 2]
    assert len(subs) == 7 * 7  # planets only
    for m in majors:
        ss = [s for s in subs if s.major_lord == m.lord]
        if m.lord in PLANET_ORDER:
            assert len(ss) == 7
            assert ss[0].lord == m.lord  # first sub-lord = major lord
            assert abs(ss[0].start_jd - m.start_jd) < 1e-9
            assert abs(ss[-1].end_jd - m.end_jd) < 1e-9
        else:
            assert ss == []


def test_firdaria_night_sequence_and_node_variants():
    f = firdaria(NIGHT, cycles=1)
    assert NIGHT.is_day is False
    lords = [p.lord for p in _majors(f)]
    assert lords == ["MOON", "SATURN", "JUPITER", "MARS",
                     "NORTH_NODE", "SOUTH_NODE",       # nodes follow Mars
                     "SUN", "VENUS", "MERCURY"]
    lords_end = [p.lord for p in _majors(firdaria(NIGHT, cycles=1, nodes="at-end"))]
    assert lords_end == ["MOON", "SATURN", "JUPITER", "MARS",
                         "SUN", "VENUS", "MERCURY", "NORTH_NODE", "SOUTH_NODE"]
    # day chart: both variants coincide
    day_am = [p.lord for p in _majors(firdaria(NATAL, cycles=1))]
    day_end = [p.lord for p in _majors(firdaria(NATAL, cycles=1, nodes="at-end"))]
    assert day_am == day_end
    assert sum(MAJOR_YEARS[x] for x in lords) == 75


def test_firdaria_requires_sect():
    import dataclasses
    unknown = dataclasses.replace(NATAL, is_day=None)
    with pytest.raises(ValueError):
        firdaria(unknown)


# ---- profections ---------------------------------------------------------------

def test_profections_cycle_and_lords():
    pr = profections(NATAL, NOW)
    asc_sign = sign_index(NATAL.angles["ASC"])
    assert pr.years[0].asc_sign == asc_sign
    for y in pr.years:
        assert y.asc_sign == (asc_sign + y.age) % 12
        assert y.year_lord == DOMICILE[y.asc_sign]
        if y.age >= 12:
            assert y.asc_sign == pr.years[y.age - 12].asc_sign
    assert pr.current is not None
    assert pr.current.start_jd <= NOW.jd_ut < pr.current.end_jd
    assert 0 <= pr.current_month_index <= 11


def test_profection_boundaries_are_solar_returns():
    from astrotext.core.chart import default_ephemeris
    eph = default_ephemeris()
    pr = profections(NATAL, NOW)
    natal_sun = NATAL.points["SUN"].lon
    for y in pr.years[1:5]:
        assert abs(angdiff(eph.state(y.start_jd, "SUN").lon, natal_sun)) < 2e-6


# ---- VOC ------------------------------------------------------------------------

def test_moon_void_consistency():
    v = compute_moon_void(NOW.jd_ut)
    assert 0 <= v.moon_sign <= 11
    assert v.sign_exit_jd > NOW.jd_ut
    if v.next_exact:
        assert v.next_exact[2] > NOW.jd_ut
        # void definition: next exact falls beyond the sign exit
        assert v.is_void == (v.next_exact[2] > v.sign_exit_jd)
        assert v.next_is_after_sign_change == (v.next_exact[2] > v.sign_exit_jd)
    if v.last_exact:
        assert v.last_exact[2] <= NOW.jd_ut
    from astrotext.core.chart import default_ephemeris
    eph = default_ephemeris()
    assert sign_index(eph.state(NOW.jd_ut, "MOON").lon) == v.moon_sign
