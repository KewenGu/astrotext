"""Property tests for the angle helpers — everything downstream leans on these."""
import math
import random

from astrotext.core.angles import angdiff, deg_to_dms, dms_to_deg, norm360

R = random.Random(12345)
SAMPLES = [R.uniform(-1e6, 1e6) for _ in range(20000)]
EDGES = [0.0, -0.0, 360.0, -360.0, 720.0, 180.0, -180.0, 359.9999999999,
         1e-12, -1e-12, 29.999999999999996]


def test_norm360_range_and_identity():
    for x in SAMPLES + EDGES:
        r = norm360(x)
        assert 0.0 <= r < 360.0, (x, r)
        # equivalence mod 360
        assert math.isclose(math.fmod(x - r, 360.0), 0.0, abs_tol=1e-6)


def test_angdiff_bounds_and_reconstruction():
    for i in range(0, len(SAMPLES) - 1, 2):
        a, b = SAMPLES[i], SAMPLES[i + 1]
        d = angdiff(a, b)
        assert -180.0 < d <= 180.0, (a, b, d)
        # b + d == a (mod 360)
        assert abs(angdiff(norm360(b + d), norm360(a))) < 1e-6


def test_angdiff_known_values():
    assert angdiff(10.0, 350.0) == 20.0
    assert angdiff(350.0, 10.0) == -20.0
    assert angdiff(190.0, 10.0) == 180.0   # +180 by convention
    assert angdiff(10.0, 190.0) == 180.0   # ...on both sides
    assert angdiff(0.0, 360.0) == 0.0
    assert angdiff(0.0, 0.0) == 0.0


def test_dms_roundtrip_and_carry():
    for dec in (0, 1, 2, 4):
        q = 0.5 / (3600 * 10 ** dec)  # half quantum
        for x in SAMPLES[:5000]:
            x = math.fmod(x, 360.0)
            sign, d, m, s = deg_to_dms(x, dec)
            assert 0 <= m < 60 and 0 <= s < 60, (x, d, m, s)
            assert abs(dms_to_deg(sign, d, m, s) - x) <= q * 1.0000001, x
    # the classic carry trap
    sign, d, m, s = deg_to_dms(29.9999999, 0)
    assert (sign, d, m, s) == (1, 30, 0, 0.0)
    sign, d, m, s = deg_to_dms(59.99999999, 2)
    assert (sign, d, m, s) == (1, 60, 0, 0.0)


def test_zodiac_helpers():
    from astrotext.core.zodiac import deg_in_sign, element, modality, sign_index
    assert sign_index(0.0) == 0 and sign_index(359.999) == 11
    assert sign_index(280.3689) == 9  # Sun @ J2000 in Capricorn
    assert abs(deg_in_sign(280.3689) - 10.3689) < 1e-9
    assert element(0) == "fire" and element(1) == "earth"
    assert modality(0) == "cardinal" and modality(4) == "fixed"
    for lon in [x % 360 for x in SAMPLES[:2000]]:
        s = sign_index(lon)
        assert 0 <= s <= 11
        assert abs(30 * s + deg_in_sign(lon) - norm360(lon)) < 1e-9


def test_canonical_signed_zero_formatting():
    """Cross-compiler ulp differences flip the sign of ~zero values (the
    node-node opposition orb); the text view must render ONE canonical
    form. Regression for the macOS -0.000/+0.000 snapshot mismatch."""
    from astrotext.render.text import sf
    for tiny in (0.0, -0.0, 1e-16, -1e-16, 4.9e-4, -4.9e-4):
        assert sf(tiny, 3) == "+0.000", tiny
    assert sf(-5.1e-4, 3) == "-0.001"
    assert sf(-0.0005001, 3) == "-0.001"
    assert sf(0.0006, 3) == "+0.001"
    assert sf(-1e-18, 6) == "+0.000000"
    # legitimately nonzero values keep their sign at display precision
    assert sf(-0.000557, 6) == "-0.000557"


def test_no_negative_zero_in_snapshots():
    import re
    from pathlib import Path
    snap_dir = Path(__file__).parents[1] / "golden" / "snapshots"
    bad = re.compile(r"-0\.0+(?:\s|\||$)")  # -0.000 style fields
    offenders = [p.name for p in snap_dir.glob("*.txt")
                 if bad.search(p.read_text(encoding="utf-8"))]
    assert not offenders, offenders
