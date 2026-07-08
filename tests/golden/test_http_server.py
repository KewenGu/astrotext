"""M8: HTTP facade — in-process server, urllib round-trips."""
import json
import threading
import urllib.parse
import urllib.request

import pytest

from astrotext.http_server import make_server

SUBJECT = {"name": "HTTP Test 1988", "birth": "1988-06-15 14:30",
           "lat": 39.9042, "lon": 116.4074, "tz": "Asia/Shanghai"}
CURRENT = {"lat": 40.7128, "lon": -74.0060, "name": "New York"}


@pytest.fixture(scope="module")
def base_url():
    srv = make_server("127.0.0.1", 0)          # OS-assigned free port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _get(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.status, r.headers.get_content_type(), r.read().decode()


def _post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.status, r.headers.get_content_type(), r.read().decode()


def test_health(base_url):
    code, ctype, body = _get(f"{base_url}/v0/health")
    doc = json.loads(body)
    assert code == 200 and doc["ok"] and doc["engine"] == "astrotext"
    assert "natal" in doc["kinds"]


def test_resolve_place_chinese(base_url):
    q = urllib.parse.quote("兰州")
    code, ctype, body = _get(f"{base_url}/v0/resolve-place?q={q}")
    doc = json.loads(body)
    assert code == 200 and doc["hits"][0]["name"] == "Lanzhou"
    assert doc["hits"][0]["tz"] == "Asia/Shanghai"


def test_chart_text_and_json(base_url):
    code, ctype, text = _post(f"{base_url}/v0/chart",
                              {"kind": "natal", "subject": SUBJECT})
    assert code == 200 and ctype == "text/plain"
    assert text.startswith("== ASTROTEXT NATAL v0 ==")
    assert text.endswith("== END ==\n")
    code, ctype, body = _post(f"{base_url}/v0/chart",
                              {"kind": "natal", "subject": SUBJECT,
                               "format": "json"})
    assert code == 200 and ctype == "application/json"
    assert json.loads(body)["format"] == "astrotext-json"


def test_chart_matches_library_bytes(base_url):
    import datetime as dt

    from astrotext.dossier import Subject, build_dossier
    from astrotext.timespace import Place
    _c, _t, text = _post(f"{base_url}/v0/chart",
                         {"kind": "vedic_rashi", "subject": SUBJECT})
    files = build_dossier(
        Subject(name="HTTP Test 1988", local=dt.datetime(1988, 6, 15, 14, 30),
                place=Place(39.9042, 116.4074, None, "Asia/Shanghai")),
        dt.datetime(1988, 6, 15, 14, 30, tzinfo=dt.timezone.utc),
        Place(39.9042, 116.4074), fmt="text")
    assert text == files["50_vedic_rashi.txt"]


def test_dossier_include(base_url):
    code, ctype, text = _post(f"{base_url}/v0/dossier",
                              {"subject": SUBJECT, "now": "2026-07-08 12:00",
                               "current": CURRENT,
                               "include": ["transits", "vedic_vimshottari"]})
    assert code == 200 and "DOSSIER-INDEX" in text
    assert "TRANSITS" in text and "VIMSHOTTARI" in text
    assert "SOLAR-ARC" not in text


def test_errors(base_url):
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(f"{base_url}/v0/chart", {"kind": "transits", "subject": SUBJECT})
    assert e.value.code == 400        # timed kind without now
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(f"{base_url}/v0/nope")
    assert e.value.code == 404
