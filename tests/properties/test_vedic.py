"""M5 invariants: sidereal layer, nakshatras, vargas, vimshottari, panchanga."""
import datetime as dt
import random
import sys
from pathlib import Path

import pytest
import swisseph as swe

sys.path.insert(0, str(Path(__file__).parents[1] / "golden"))

from astrotext.core.angles import angdiff, norm360  # noqa: E402
from astrotext.core.chart import default_ephemeris  # noqa: E402
from astrotext.techniques.vedic import (  # noqa: E402
    DASHA_YEARS, GRAHA_ORDER, NAKSHATRAS, compute_vedic_chart, nakshatra_of,
    varga_sign, vargottama, vimshottari,
)
from astrotext.techniques.vedic.panchanga import compute as panchanga  # noqa: E402
from astrotext.timespace import Place, resolve  # noqa: E402
from astrotext.verify import swetest_ref  # noqa: E402

BEIJING = Place(39.9042, 116.4074, "Beijing", "Asia/Shanghai")
M = resolve(dt.datetime(1988, 6, 15, 14, 30), BEIJING)
VC = compute_vedic_chart(M)
RNG = random.Random(5150)


# ---- sidereal core ----------------------------------------------------------

def test_sidereal_matches_swetest_sid1():
    """Native FLG_SIDEREAL must agree with `swetest -sid1` bit-for-bit."""
    eph = default_ephemeris()
    eph.configure_sidereal("lahiri")
    jds = [2451545.0, M.jd_ut] + [RNG.uniform(swe.julday(1900, 1, 5, 0),
                                              swe.julday(2100, 12, 25, 0))
                                  for _ in range(6)]
    import subprocess
    from astrotext import config
    for jd in jds:
        out = subprocess.run(
            [str(config.swetest_bin()), f"-edir{config.ephe_path()}",
             f"-bj{jd!r}", "-ut", "-p0123456", "-sid1", "-fPlbs", "-head"],
            capture_output=True, text=True, timeout=60).stdout
        import re
        for line in out.splitlines():
            m = re.match(r"^(\w[\w ]*?)\s+(-?\d+\.\d+)", line)
            if not m:
                continue
            name = m.group(1).strip()
            key = {"Sun": "SUN", "Moon": "MOON", "Mercury": "MERCURY",
                   "Venus": "VENUS", "Mars": "MARS", "Jupiter": "JUPITER",
                   "Saturn": "SATURN"}.get(name)
            if key:
                ours = eph.state(jd, key, sidereal=True).lon
                assert abs(angdiff(ours, float(m.group(2)))) <= 2e-7, (key, jd)


def test_tropical_minus_sidereal_uniform_across_points():
    eph = default_ephemeris()
    eph.configure_sidereal("lahiri")
    jd = M.jd_ut
    diffs = []
    for key in ("SUN", "MOON", "MARS", "JUPITER", "SATURN", "MEAN_NODE"):
        t = eph.state(jd, key).lon
        s = eph.state(jd, key, sidereal=True).lon
        diffs.append(norm360(t - s))
    for d in diffs[1:]:
        assert abs(d - diffs[0]) < 1e-9  # one ayanamsa for everything
    # trop-sid differs from get_ayanamsa_ut by ~nutation (<=18 arcsec):
    # SE applies the ayanamsa on the mean equinox for sidereal positions.
    assert abs(diffs[0] - eph.ayanamsa(jd)) < 6e-3
    assert abs(diffs[0] - 23.6967) < 1e-3  # Lahiri mid-1988 (position-based)


def test_rahu_ketu_opposition_and_houses():
    r, k = VC.grahas["RAHU"], VC.grahas["KETU"]
    assert abs(angdiff(k.lon, r.lon + 180.0)) < 1e-12
    assert (k.house - r.house) % 12 == 6
    for g in VC.grahas.values():
        assert 1 <= g.house <= 12
        assert g.house == ((g.sign - VC.lagna_sign) % 12) + 1


# ---- nakshatra ---------------------------------------------------------------

def test_nakshatra_boundaries_and_lords():
    assert len(NAKSHATRAS) == 27
    n0 = nakshatra_of(0.0)
    assert (n0.index, n0.name, n0.pada, n0.lord) == (0, "Ashwini", 1, "KETU")
    n1 = nakshatra_of(360.0 / 27.0)
    assert (n1.name, n1.lord) == ("Bharani", "VENUS")
    n_last = nakshatra_of(359.9999)
    assert (n_last.name, n_last.lord, n_last.pada) == ("Revati", "MERCURY", 4)
    # pada arithmetic: 3deg20' quarters
    assert nakshatra_of(3.3334).pada == 2
    assert nakshatra_of(9.9999).pada == 3
    assert nakshatra_of(10.0001).pada == 4
    # lord cycle period 9
    for i in range(200):
        lon = RNG.uniform(0, 360)
        n = nakshatra_of(lon)
        assert n.lord == nakshatra_of(norm360(lon + 9 * 360.0 / 27.0)).lord
        assert 0.0 <= n.fraction < 1.0


# ---- vargas --------------------------------------------------------------------

ALL_VARGAS = (1, 2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60)


def test_varga_outputs_valid_and_d1_identity():
    for _ in range(400):
        lon = RNG.uniform(0, 360)
        for d in ALL_VARGAS:
            s, part = varga_sign(lon, d)
            assert 0 <= s <= 11
            assert part >= 0
        assert varga_sign(lon, 1)[0] == int(norm360(lon) // 30)


def test_navamsa_formula_equals_element_rule():
    """(sign*9+part)%12 must equal the classical element-start statement."""
    starts = {0: 0, 1: 9, 2: 6, 3: 3}  # fire->Ari, earth->Cap, air->Lib, water->Can
    for _ in range(400):
        lon = RNG.uniform(0, 360)
        sign = int(norm360(lon) // 30)
        part = int((norm360(lon) % 30) // (30.0 / 9.0))
        expect = (starts[sign % 4] + part) % 12
        assert varga_sign(lon, 9)[0] == expect


def test_hora_only_leo_or_cancer_and_d2_rule():
    for _ in range(200):
        lon = RNG.uniform(0, 360)
        s, _ = varga_sign(lon, 2)
        assert s in (3, 4)  # Cancer or Leo only (Parashara hora)
    assert varga_sign(10.0, 2)[0] == 4    # 10 Aries (odd, 1st half) -> Leo
    assert varga_sign(20.0, 2)[0] == 3    # 20 Aries -> Cancer
    assert varga_sign(40.0, 2)[0] == 3    # 10 Taurus (even, 1st half) -> Cancer
    assert varga_sign(50.0, 2)[0] == 4    # 20 Taurus -> Leo


def test_d30_spans_and_signs():
    # odd sign (Aries): Mars5/Sat5/Jup8/Mer7/Ven5 -> Ari/Aqu/Sag/Gem/Lib
    for deg, sign in [(2, 0), (7, 10), (12, 8), (20, 2), (27, 6)]:
        assert varga_sign(deg, 30)[0] == sign, deg
    # even sign (Taurus): Ven5/Mer7/Jup8/Sat5/Mars5 -> Tau/Vir/Pis/Cap/Sco
    for deg, sign in [(2, 1), (8, 5), (15, 11), (22, 9), (28, 7)]:
        assert varga_sign(30 + deg, 30)[0] == sign, deg


def test_d60_counts_from_own_sign():
    # 29 Gemini: part 58 -> (2 + 58) % 12 = 0 (Aries)
    assert varga_sign(89.0, 60)[0] == 0
    assert varga_sign(60.0, 60)[0] == 2   # 0 Gemini -> Gemini itself


def test_vargottama_definition():
    for _ in range(300):
        lon = RNG.uniform(0, 360)
        assert vargottama(lon) == (varga_sign(lon, 1)[0] == varga_sign(lon, 9)[0])
    assert vargottama(1.0)      # 1 Aries: D9 part 0 -> Aries
    assert not vargottama(29.0)  # 29 Aries -> D9 Sagittarius


# ---- vimshottari ----------------------------------------------------------------

def test_dasha_years_sum_and_sequence():
    assert sum(DASHA_YEARS.values()) == 120
    periods = vimshottari(VC.grahas["MOON"].lon, M.jd_ut)
    majors = [p for p in periods if p.level == 1]
    antars = [p for p in periods if p.level == 2]
    pratys = [p for p in periods if p.level == 3]
    assert (len(majors), len(antars), len(pratys)) == (9, 81, 729)
    assert majors[0].lord == VC.grahas["MOON"].nak.lord  # Ardra -> RAHU
    # gapless nesting at every level
    for parent, kids in ((1, antars), (2, pratys)):
        pass
    for m1, m2 in zip(majors, majors[1:]):
        assert abs(m1.end_jd - m2.start_jd) < 1e-9
    for level, group in ((2, antars), (3, pratys)):
        for p in [x for x in periods if x.level == level - 1]:
            kids = [k for k in group if k.lords[:level - 1] == p.lords]
            assert len(kids) == 9
            assert abs(kids[0].start_jd - p.start_jd) < 1e-6
            assert abs(kids[-1].end_jd - p.end_jd) < 1e-6
            assert kids[0].lord == p.lord  # first sub-lord = parent lord
    # total cycle = 120 years
    assert abs((majors[-1].end_jd - majors[0].start_jd) - 120 * 365.25) < 1e-6


def test_dasha_balance_at_birth():
    periods = vimshottari(VC.grahas["MOON"].lon, M.jd_ut)
    first = periods[0]
    nak = VC.grahas["MOON"].nak
    expected_balance = (1.0 - nak.fraction) * DASHA_YEARS[nak.lord] * 365.25
    assert abs((first.end_jd - M.jd_ut) - expected_balance) < 1e-6
    assert first.start_jd < M.jd_ut <= first.end_jd


# ---- panchanga -------------------------------------------------------------------

def test_panchanga_arithmetic():
    p = panchanga(0.0, 0.0)
    assert (p.tithi_index, p.tithi, p.paksha) == (0, "Shukla Pratipada", "Shukla")
    assert p.karana == "Kimstughna"
    p = panchanga(0.0, 179.9)          # just before full
    assert p.tithi == "Purnima" and p.paksha == "Shukla"
    p = panchanga(0.0, 359.9)          # just before new
    assert p.tithi == "Amavasya" and p.paksha == "Krishna"
    assert p.karana == "Naga"          # last karana
    p = panchanga(10.0, 10.0 + 6.5)    # second half-tithi
    assert p.karana == "Bava"          # first movable
    # yoga: sum arithmetic (avoid exact boundaries; float 360/27 rounds up)
    p = panchanga(100.0, 105.0)        # sum 205 -> 205*27/360 = 15.375 -> idx 15
    assert p.yoga_index == 15
    p = panchanga(0.0, 13.0)           # sum 13 < 13deg20' -> idx 0 Vishkambha
    assert p.yoga_index == 0 and p.yoga == "Vishkambha"
    # invariance of tithi under ayanamsa shift (difference-based)
    for _ in range(50):
        s, mo, ay = RNG.uniform(0, 360), RNG.uniform(0, 360), RNG.uniform(0, 30)
        assert panchanga(s, mo).tithi_index == \
            panchanga(norm360(s - ay), norm360(mo - ay)).tithi_index


def test_vedic_chart_karakas_consistency():
    assert [k for k, _, _ in VC.karakas] == ["AK", "AmK", "BK", "MK",
                                             "PiK", "PuK", "GK", "DK"]
    advs = [d for _, _, d in VC.karakas]
    assert advs == sorted(advs, reverse=True)
    rahu_deg = [d for _, g, d in VC.karakas if g == "RAHU"]
    assert rahu_deg and abs(rahu_deg[0] - (30.0 - VC.grahas["RAHU"].sign_deg)) < 1e-9
