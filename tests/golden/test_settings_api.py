"""M8b: request-level settings — parsing, threading, and facade behavior."""
import json

import pytest

from astrotext.options import TechOptions, parse_settings, settings_cache_key


def test_defaults_when_absent():
    s, v, t = parse_settings(None)
    assert s.house_system == "P" and s.node == "true"
    assert v.ayanamsa == "lahiri" and v.node == "mean"
    assert t == TechOptions()


def test_western_knobs():
    s, v, t = parse_settings({"house_system": "W", "node": "mean",
                              "aspects": "majors", "angle_orb": 2.0})
    assert s.house_system == "W"
    assert "MEAN_NODE" in s.points and "TRUE_NODE" not in s.points
    assert all(a.major for a in s.aspects)
    assert s.angle_orb == 2.0


def test_vedic_and_tech_knobs():
    s, v, t = parse_settings({
        "transit_orb": 1.5, "return_precessed": True,
        "firdaria_nodes": "at-end", "progression_year": "julian",
        "vedic": {"ayanamsa": "krishnamurti", "node": "true",
                  "karaka_scheme": 7, "dasha_max_level": 2,
                  "vargas": [9, 1, 10]}})
    assert t.transit_orb == 1.5 and t.return_precessed is True
    assert t.firdaria_nodes == "at-end" and t.progression_year == "julian"
    assert v.ayanamsa == "krishnamurti" and v.node == "true"
    assert v.karaka_scheme == 7 and v.vargas == (1, 9, 10)
    assert t.dasha_max_level == 2


@pytest.mark.parametrize("bad", [
    {"hous_system": "W"},                       # typo -> reject, never ignore
    {"house_system": "Z"},
    {"node": "osculating"},
    {"angle_orb": 99},
    {"vedic": {"ayanamsa": "lahiri", "extra": 1}},
    {"vedic": {"vargas": [11]}},                # D11 not in Shodashavarga set
    {"vedic": {"dasha_max_level": 4}},
    {"return_precessed": "yes"},
])
def test_invalid_settings_rejected(bad):
    with pytest.raises(ValueError):
        parse_settings(bad)


def test_cache_key_canonical():
    a = settings_cache_key({"node": "mean", "house_system": "W"})
    b = settings_cache_key({"house_system": "W", "node": "mean"})
    assert a == b
    assert settings_cache_key(None) == settings_cache_key({})


# ---- end to end through the HTTP facade -------------------------------------

import threading  # noqa: E402
import urllib.request  # noqa: E402

from astrotext.http_server import make_server  # noqa: E402

SUBJECT = {"birth": "1988-06-15 14:30", "lat": 39.9042, "lon": 116.4074,
           "tz": "Asia/Shanghai"}


@pytest.fixture(scope="module")
def base_url():
    srv = make_server("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read().decode()


def test_http_house_system_setting(base_url):
    default = _post(f"{base_url}/v0/chart",
                    {"kind": "natal", "subject": SUBJECT})
    whole = _post(f"{base_url}/v0/chart",
                  {"kind": "natal", "subject": SUBJECT,
                   "settings": {"house_system": "W"}})
    assert "houses-used=P" in default and "houses-used=W" in whole
    assert "HOUSES (W)" in whole and default != whole


def test_http_ayanamsa_setting(base_url):
    lahiri = _post(f"{base_url}/v0/chart",
                   {"kind": "vedic_rashi", "subject": SUBJECT})
    kp = _post(f"{base_url}/v0/chart",
               {"kind": "vedic_rashi", "subject": SUBJECT,
                "settings": {"vedic": {"ayanamsa": "krishnamurti"}}})
    assert "set:ayanamsa=lahiri" in lahiri
    assert "set:ayanamsa=krishnamurti" in kp
    ay = lambda t: float(next(l for l in t.splitlines()
                              if l.startswith("ayanamsa-value=")).split("=")[1])
    assert 0.05 < abs(ay(lahiri) - ay(kp)) < 0.2  # KP differs ~6 arcmin

def test_http_firdaria_node_variant(base_url):
    end = _post(f"{base_url}/v0/chart",
                {"kind": "firdaria", "subject": SUBJECT,
                 "now": "2026-07-08 12:00",
                 "current": {"lat": 40.71, "lon": -74.0},
                 "settings": {"firdaria_nodes": "at-end"}})
    assert "node-placement=at-end" in end


def test_http_bad_settings_400(base_url):
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(f"{base_url}/v0/chart",
              {"kind": "natal", "subject": SUBJECT,
               "settings": {"hous_system": "W"}})
    assert e.value.code == 400
    body = json.loads(e.value.read().decode())
    assert "unknown keys" in body["error"]
