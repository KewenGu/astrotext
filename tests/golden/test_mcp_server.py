"""M7: MCP stdio server round-trip via a real subprocess."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]

SUBJECT = {"name": "MCP Test 1988", "birth": "1988-06-15 14:30",
           "lat": 39.9042, "lon": 116.4074, "tz": "Asia/Shanghai",
           "place_name": "Beijing"}
CURRENT = {"lat": 40.7128, "lon": -74.0060, "name": "New York"}


def _run_mcp(requests: list[dict]) -> list[dict]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        str(ROOT / p) for p in ("src", "vendor/py", "vendor/lib"))
    env.setdefault("SE_EPHE_PATH", str(ROOT / "data" / "ephe"))
    inp = "".join(json.dumps(r) + "\n" for r in requests)
    out = subprocess.run([sys.executable, "-m", "astrotext", "mcp"],
                         input=inp, capture_output=True, text=True,
                         env=env, timeout=180)
    assert out.returncode == 0, out.stderr[-800:]
    return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]


def test_mcp_full_session():
    resps = _run_mcp([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "astro_chart",
                    "arguments": {"kind": "natal", "subject": SUBJECT}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "astro_chart",
                    "arguments": {"kind": "vedic_rashi", "subject": SUBJECT}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "astro_dossier",
                    "arguments": {"subject": SUBJECT, "now": "2026-07-08 12:00",
                                  "current": CURRENT,
                                  "include": ["transits", "profections"]}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
         "params": {"name": "astro_chart",
                    "arguments": {"kind": "transits", "subject": SUBJECT}}},
        {"jsonrpc": "2.0", "id": 7, "method": "nonexistent/method"},
        {"jsonrpc": "2.0", "id": 8, "method": "tools/call",
         "params": {"name": "astro_resolve_place",
                    "arguments": {"query": "\u5170\u5dde"}}},
    ])
    by_id = {r.get("id"): r for r in resps}
    assert by_id[1]["result"]["protocolVersion"] == "2024-11-05"
    assert by_id[1]["result"]["serverInfo"]["name"] == "astrotext"
    tools = {t["name"] for t in by_id[2]["result"]["tools"]}
    assert tools == {"astro_chart", "astro_dossier", "astro_resolve_place"}
    natal = by_id[3]["result"]["content"][0]["text"]
    assert natal.startswith("== ASTROTEXT NATAL v0 ==") and natal.endswith("== END ==\n")
    rashi = by_id[4]["result"]["content"][0]["text"]
    assert "VEDIC-RASHI" in rashi.splitlines()[0]
    dossier = by_id[5]["result"]["content"][0]["text"]
    assert "DOSSIER-INDEX" in dossier and "TRANSITS" in dossier and "PROFECTIONS" in dossier
    assert "VIMSHOTTARI" not in dossier  # not in include list
    # timed kind without 'now' -> tool error, not crash
    assert by_id[6]["result"].get("isError") is True
    assert by_id[7]["error"]["code"] == -32601
    place = by_id[8]["result"]["content"][0]["text"]
    assert "Lanzhou" in place and "Asia/Shanghai" in place


def test_mcp_chart_matches_cli_output(tmp_path):
    """The MCP tool must return byte-identical text to the dossier writer."""
    import datetime as dt

    from astrotext.dossier import Subject, build_dossier
    from astrotext.timespace import Place
    resps = _run_mcp([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "astro_chart",
                    "arguments": {"kind": "solar_return", "subject": SUBJECT,
                                  "now": "2026-07-08 12:00",
                                  "current": CURRENT}}},
    ])
    text = [r for r in resps if r.get("id") == 2][0]["result"]["content"][0]["text"]
    files = build_dossier(
        Subject(name="MCP Test 1988", local=dt.datetime(1988, 6, 15, 14, 30),
                place=Place(39.9042, 116.4074, "Beijing", "Asia/Shanghai")),
        dt.datetime(2026, 7, 8, 12, 0, tzinfo=dt.timezone.utc),
        Place(40.7128, -74.0060, "New York"), fmt="text")
    assert text == files["30_solar_return.txt"]
