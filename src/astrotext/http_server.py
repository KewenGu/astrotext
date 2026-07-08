"""HTTP facade — the same engine behind REST-ish URLs (stdlib only).

Run:  python -m astrotext http [--host 127.0.0.1] [--port 8747]

Routes (v0):
  GET  /v0/health                          liveness + engine versions
  GET  /v0/resolve-place?q=北京&country=CN&limit=5
  POST /v0/chart      {"kind": "...", "subject": {...},
                       "now"?: "YYYY-MM-DD HH:MM" (UTC),
                       "current"?: {lat, lon, name?},
                       "format"?: "text"|"json"}
  POST /v0/dossier    {"subject": {...}, "now": "...", "current": {...},
                       "include"?: ["transits", ...],
                       "format"?: "text"|"json"}

Design decisions:
* Birth data is PERSONAL data: it travels in POST bodies, never in URLs
  (query strings end up in access logs and proxies).  The only GET with
  parameters is place resolution — place names are not personal.
* Responses: text/plain for format=text (the exact bytes the CLI writes),
  application/json otherwise.  Errors: {"error": "..."} with 4xx/5xx.
* Binds 127.0.0.1 by default — this server has NO auth; put it behind a
  reverse proxy if it must be reachable from elsewhere.
* Same LRU-cached compute as the MCP server: one subject, many pulls.
"""
from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import ENGINE_NAME, __version__
from .mcp_server import (  # shared compute + validation
    _KINDS, _STEM, _call_astro_chart, _dossier_cached, _subject_key,
)

__all__ = ["serve", "make_server"]

_MAX_BODY = 1 << 20  # 1 MiB: any legitimate request is far smaller


def _chart(payload: dict) -> tuple[int, str, str]:
    text = _call_astro_chart(payload)
    ctype = ("text/plain; charset=utf-8"
             if payload.get("format", "text") == "text"
             else "application/json; charset=utf-8")
    return 200, ctype, text


def _dossier(payload: dict) -> tuple[int, str, str]:
    subject = payload["subject"]
    cur = payload["current"]
    fmt = payload.get("format", "text")
    files = _dossier_cached(_subject_key(subject), payload["now"],
                            (float(cur["lat"]), float(cur["lon"]),
                             cur.get("name")), fmt)
    include = payload.get("include")
    stems = ([_STEM[k] for k in include if k in _STEM] if include
             else list(_STEM.values()))
    if fmt == "json":
        picked = {n: files[n] for n in files
                  if n.endswith(".json") and n[:-5] in stems}
        body = json.dumps({"format": "astrotext-json-dossier",
                           "files": picked}, ensure_ascii=False)
        return 200, "application/json; charset=utf-8", body
    parts = [files["index.txt"], files["00_meta.txt"]]
    parts += [files[f"{s}.txt"] for s in stems if f"{s}.txt" in files]
    return 200, "text/plain; charset=utf-8", "\n".join(parts)


def _resolve(query: dict) -> tuple[int, str, str]:
    from .timespace.gazetteer import lookup
    q = (query.get("q") or query.get("query") or [""])[0]
    if not q:
        return 400, "application/json; charset=utf-8", \
            json.dumps({"error": "missing q= parameter"})
    country = (query.get("country") or [None])[0]
    limit = int((query.get("limit") or ["5"])[0])
    hits = lookup(q, country, limit)
    body = json.dumps({"query": q, "country": country, "hits": [
        {"name": h.name, "label": h.label(), "lat": h.lat, "lon": h.lon,
         "tz": h.tz, "country": h.country, "admin1": h.admin1,
         "population": h.population, "matched_on": h.matched_on}
        for h in hits]}, ensure_ascii=False)
    return 200, "application/json; charset=utf-8", body


class _Handler(BaseHTTPRequestHandler):
    server_version = f"astrotext/{__version__}"

    def _send(self, code: int, ctype: str, body: str) -> None:
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _fail(self, code: int, msg: str) -> None:
        self._send(code, "application/json; charset=utf-8",
                   json.dumps({"error": msg}, ensure_ascii=False))

    def log_message(self, fmt, *args):  # quiet by default; PATHS ONLY —
        pass                            # bodies (birth data) never logged

    def do_GET(self) -> None:  # noqa: N802
        url = urllib.parse.urlparse(self.path)
        if url.path == "/v0/health":
            self._send(200, "application/json; charset=utf-8", json.dumps({
                "ok": True, "engine": ENGINE_NAME, "version": __version__,
                "kinds": _KINDS}))
            return
        if url.path == "/v0/resolve-place":
            try:
                self._send(*_resolve(urllib.parse.parse_qs(url.query)))
            except Exception as exc:
                self._fail(500, f"{type(exc).__name__}: {exc}")
            return
        self._fail(404, f"no route {url.path!r}; see docs/API.md")

    def do_POST(self) -> None:  # noqa: N802
        url = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        if n > _MAX_BODY:
            self._fail(413, "body too large")
            return
        try:
            payload = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            self._fail(400, "body must be valid JSON")
            return
        try:
            if url.path == "/v0/chart":
                self._send(*_chart(payload))
            elif url.path == "/v0/dossier":
                self._send(*_dossier(payload))
            else:
                self._fail(404, f"no route {url.path!r}; see docs/API.md")
        except (KeyError, ValueError) as exc:
            self._fail(400, f"{type(exc).__name__}: {exc}")
        except Exception as exc:
            self._fail(500, f"{type(exc).__name__}: {exc}")


def make_server(host: str = "127.0.0.1", port: int = 8747) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), _Handler)


def serve(host: str = "127.0.0.1", port: int = 8747) -> int:
    srv = make_server(host, port)
    print(f"astrotext http: listening on http://{host}:{port}/v0/health "
          f"(no auth — keep it local or proxy it)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
