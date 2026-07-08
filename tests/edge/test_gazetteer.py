"""M6: offline gazetteer — resolution, Chinese names, ambiguity, misses.

Skipped wholesale when the compiled data file is absent (fresh clones
before running tools/build_gazetteer.py)."""
import pytest

from astrotext.timespace.gazetteer import (
    PlaceNotFound, available, lookup, resolve_place,
)

pytestmark = pytest.mark.skipif(not available(),
                                reason="gazetteer data not built")


def test_chinese_domestic_names():
    for q, expect_tz, expect_country in [
        ("北京", "Asia/Shanghai", "China"),
        ("上海", "Asia/Shanghai", "China"),
        ("广州", "Asia/Shanghai", "China"),
        ("深圳", "Asia/Shanghai", "China"),
        ("成都", "Asia/Shanghai", "China"),
        ("西安", "Asia/Shanghai", "China"),
        ("乌鲁木齐", "Asia/Urumqi", "China"),   # the OTHER Chinese zone
        ("香港", "Asia/Hong_Kong", "Hong Kong"),
        ("台北", "Asia/Taipei", "Taiwan"),
        ("东京", "Asia/Tokyo", "Japan"),
        ("莫斯科", "Europe/Moscow", "Russia"),
    ]:
        hits = lookup(q)
        assert hits, q
        assert hits[0].tz == expect_tz, (q, hits[0])
        assert hits[0].country == expect_country, (q, hits[0])


def test_every_zh_exonym_supplement_entry_resolves():
    """The curated table maps NAMES only; each entry must resolve in the
    gazetteer or it is a bug in the table."""
    from astrotext.timespace.zh_exonyms import ZH_EXONYMS
    for zh, (query, country) in ZH_EXONYMS.items():
        hits = lookup(zh)
        assert hits, f"supplement entry {zh!r} -> {query!r} does not resolve"
        assert hits[0].matched_on == "zh-exonym-supplement", zh
        direct = lookup(query, country)
        assert direct and hits[0].name == direct[0].name, (zh, hits[0], direct[:1])
        # guard against alias collisions resolving to hamlets (Venice proper
        # is only ~51k residents — the historic city, correct):
        assert hits[0].population >= 40000, (zh, hits[0])


def test_known_coordinates_sanity():
    b = lookup("北京")[0]
    assert abs(b.lat - 39.9) < 0.2 and abs(b.lon - 116.4) < 0.2
    ny = lookup("纽约")[0]
    assert abs(ny.lat - 40.7) < 0.2 and abs(ny.lon + 74.0) < 0.2
    assert ny.tz == "America/New_York"


def test_ambiguity_flags_and_country_filter():
    place, flags = resolve_place("Cambridge")
    assert any(f.startswith("place-ambiguous") for f in flags)
    assert place.tz == "Europe/London"  # highest population wins
    us = lookup("Cambridge", "US")[0]
    assert us.admin1 == "Massachusetts"
    place_us, flags_us = resolve_place("Cambridge", "US")
    assert place_us.tz == "America/New_York"


def test_population_ranking():
    hits = lookup("Springfield", "US", limit=5)
    pops = [h.population for h in hits]
    assert pops == sorted(pops, reverse=True)
    assert len(hits) >= 3


def test_miss_raises_with_guidance():
    with pytest.raises(PlaceNotFound) as e:
        resolve_place("Xyzzy Nonexistent Town 12345")
    assert "lat/lon" in str(e.value)


def test_resolved_place_is_chartable():
    """End-to-end: gazetteer place -> timezone resolution -> chart."""
    import datetime as dt

    from astrotext.core import compute_chart
    from astrotext.timespace import resolve
    place, flags = resolve_place("兰州")
    assert place.tz == "Asia/Shanghai"
    m = resolve(dt.datetime(1990, 5, 1, 8, 0), place)
    c = compute_chart(m)
    assert len(c.points) > 0
    assert any(f.startswith("place-resolved") for f in flags)


def test_cjk_admin_suffix_normalization():
    """GeoNames stores 江阴市; users type 江阴. Regression for the
    county-level-city miss (Jiangyin, pop 1.78M)."""
    h = lookup("江阴")[0]
    assert h.name == "Jiangyin" and h.admin1 == "Jiangsu"
    assert h.tz == "Asia/Shanghai"
    assert "zh-suffix:+市" in h.matched_on
    # suffixed input still resolves (directly, no normalization needed)
    h2 = lookup("江阴市")[0]
    assert h2.name == "Jiangyin"
    # a sweep of county-level cities users actually type
    for q, name in [("昆山", "Kunshan"), ("义乌", "Yiwu"), ("慈溪", "Cixi"),
                    ("浦东", "Pudong"), ("石家庄", "Shijiazhuang")]:
        assert lookup(q)[0].name == name, q


def test_suffix_normalization_only_for_cjk():
    """Latin misses must NOT get suffix retries (or spurious matches)."""
    with pytest.raises(PlaceNotFound):
        resolve_place("Xyzzy Nonexistent Town 12345")
    assert lookup("Xyzzy Nonexistent") == []
