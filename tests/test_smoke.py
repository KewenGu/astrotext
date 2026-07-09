import pytest

pytestmark = pytest.mark.smoke


def test_imports_and_versions(eph):
    import astrotext
    assert astrotext.__version__
    if eph.backend == "swiss":
        import swisseph as swe
        assert swe.version == "2.10.03"


def test_ephemeris_files_present(eph):
    info = eph.info()
    if eph.backend == "swiss":
        needed = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")
        hint = "run `make vendor`"
    else:
        needed = ("de440_1799_2400.bsp", "chiron_horizons.npz",
                  "se_deltat_parity.csv", "hipparcos_22.json")
        hint = "run tools/fetch_kernel_data.py + tools/fetch_chiron.py"
    for f in needed:
        assert f in info["ephe_files"], f"missing {f}: {hint}"


def test_no_silent_moshier_fallback(eph):
    if eph.backend != "swiss":
        __import__("pytest").skip("moshier fallback is a swiss-only hazard")
    import swisseph as swe
    _, retflags = swe.calc_ut(2451545.0, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SPEED)
    assert retflags & swe.FLG_SWIEPH


def test_sun_j2000_against_published_value(eph):
    """Independent literature anchor: apparent geocentric longitude of the Sun
    at J2000.0 (2000-01-01 12:00 UT) is 280.36892 deg (Astronomical Almanac /
    Meeus).  This check does NOT depend on swetest."""
    st = eph.state(2451545.0, "SUN")
    assert abs(st.lon - 280.36892) < 3e-4  # within ~1 arcsec of literature
    assert abs(st.lat) < 3e-4
    assert 0.98328 < st.dist_au < 0.98338
    assert 1.016 < st.lon_speed < 1.022
