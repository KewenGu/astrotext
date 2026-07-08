"""JSON view: validity, determinism, and value-fidelity vs the objects."""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fixtures import ALL, TIMED_NOW_UTC, TIMED_PLACE, build  # noqa: E402

from astrotext.dossier import Subject, generate_dossier  # noqa: E402
from astrotext.render.json_out import chart_to_dict, to_json  # noqa: E402
from astrotext.timespace import Place  # noqa: E402

SUBJECT = Subject(
    name="Json Test 1988",
    local=dt.datetime(1988, 6, 15, 14, 30),
    place=Place(39.9042, 116.4074, "Beijing", "Asia/Shanghai"),
)


def test_chart_json_full_precision_roundtrip():
    fx = next(f for f in ALL if f.slug == "beijing-dst")
    _, c, hour, stars = build(fx)
    doc = json.loads(to_json(chart_to_dict(c, fx.name, hour, stars)))
    assert doc["format"] == "astrotext-json" and doc["format_version"] == 0
    for k, p in c.points.items():
        jp = doc["points"][k]
        assert jp["lon"] == p.lon            # exact doubles, no display rounding
        assert jp["lon_speed"] == p.lon_speed
        assert jp["retrograde"] == p.retrograde
        assert jp["house"] == p.house
    assert doc["angles"]["ASC"] == c.angles["ASC"]
    assert doc["cusps"] == list(c.cusps)
    assert len(doc["aspects"]) == len(c.aspects)
    assert doc["aspects"][0]["orb_signed"] == c.aspects[0].orb_signed
    assert doc["warnings"] == list(c.flags)
    assert doc["moment"]["jd_ut"] == c.moment.jd_ut


def test_json_deterministic_and_sorted():
    fx = next(f for f in ALL if f.slug == "einstein")
    _, c, hour, stars = build(fx)
    a = to_json(chart_to_dict(c, fx.name, hour, stars))
    b = to_json(chart_to_dict(c, fx.name, hour, stars))
    assert a == b
    doc = json.loads(a)
    assert list(doc.keys()) == sorted(doc.keys())


def test_dossier_formats(tmp_path):
    both = generate_dossier(SUBJECT, TIMED_NOW_UTC, TIMED_PLACE,
                            tmp_path / "b", fmt="both")
    txts = {p.name for p in both.glob("*.txt")}
    jsons = {p.name for p in both.glob("*.json")}
    assert len(jsons) == 13  # every data file has a json sibling
    assert {n.replace(".json", ".txt") for n in jsons} <= txts
    for p in both.glob("*.json"):
        json.loads(p.read_text(encoding="utf-8"))  # all valid

    jonly = generate_dossier(SUBJECT, TIMED_NOW_UTC, TIMED_PLACE,
                             tmp_path / "j", fmt="json")
    assert {p.name for p in jonly.glob("*.txt")} == {"index.txt", "00_meta.txt"}
    assert len({p.name for p in jonly.glob("*.json")}) == 13

    tonly = generate_dossier(SUBJECT, TIMED_NOW_UTC, TIMED_PLACE,
                             tmp_path / "t", fmt="text")
    assert len({p.name for p in tonly.glob("*.json")}) == 0


def test_json_and_text_agree_at_display_precision(tmp_path):
    """The two views must describe the same chart: text lon (6dp) equals the
    JSON double rounded to 6dp, for every point in the natal file."""
    out = generate_dossier(SUBJECT, TIMED_NOW_UTC, TIMED_PLACE,
                           tmp_path / "x", fmt="both")
    from astrotext.render.parse import parse
    tdoc = parse((out / "10_natal.txt").read_text(encoding="utf-8"))
    jdoc = json.loads((out / "10_natal.json").read_text(encoding="utf-8"))
    for row in tdoc["sections"]["POINTS"]:
        key, lon_txt = row[0], float(row[3])
        assert abs(jdoc["points"][key]["lon"] - lon_txt) < 5e-7, key
