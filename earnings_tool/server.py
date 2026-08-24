"""Interfaz web: escribe un ticker y obtén el reporte.

`handle_request` es independiente del transporte para poder usarla tanto en el
servidor local (stdlib) como en una función serverless (Vercel, api/index.py).
"""
from __future__ import annotations

import html
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .analysis import analyze
from .data import TickerNotFound, fetch_report
from .report_html import CSS, full_page, render_html

_cache: dict = {}
_lock = threading.Lock()
DEFAULT_EVENTS = 20


def _get(ticker: str, n: int):
    key = (ticker.upper(), n)
    with _lock:
        if key in _cache:
            return _cache[key]
    report = fetch_report(ticker, n_events=n)
    stats = analyze(report)
    with _lock:
        _cache[key] = (report, stats)
    return report, stats


def _home(msg: str = "") -> str:
    return full_page(f"""<title>Análisis de earnings</title><style>{CSS}</style>
<div class="wrap" style="max-width:640px;padding-top:80px">
<h1>Análisis de earnings</h1>
<div class="sub">Escribe un ticker y analiza sus últimos 20 resultados: beat/miss, sorpresa de EPS, reacción del precio, consenso de analistas y expectativa del próximo earning.</div>
<form class="search" action="/report" method="get"><input name="ticker" placeholder="Ticker (p.ej. NVDA)" autofocus required><button>Analizar</button></form>
{f"<div class='card' style='border-color:var(--neg)'>{html.escape(msg)}</div>" if msg else ""}
<div class="note">Ejemplos: AAPL · MSFT · NVDA · AMZN · GOOGL · META · TSLA · JPM · Fuente: Yahoo Finance</div></div>""")


def _stats_json(stats: dict) -> dict:
    return {k: (v.__dict__ if hasattr(v, "__dict__") else v) for k, v in stats.items()}


def handle_request(path: str, n_default: int = DEFAULT_EVENTS):
    """Devuelve (status, content_type, body) para una ruta GET (path con query)."""
    u = urlparse(path)
    q = parse_qs(u.query)
    ticker = (q.get("ticker") or [""])[0].strip()
    try:
        n = max(1, min(int((q.get("n") or [n_default])[0]), 40))
    except ValueError:
        n = n_default
    want_json = u.path.startswith("/api/report") or (q.get("format") or [""])[0] == "json"
    HTML = "text/html; charset=utf-8"

    if u.path in ("/", "") or (u.path.startswith("/api") and not ticker and not want_json):
        return 200, HTML, _home()
    if u.path in ("/report", "/api/report", "/api", "/api/index"):
        if not ticker:
            return 400, HTML, _home("Indica un ticker.")
        try:
            report, stats = _get(ticker, n)
        except TickerNotFound as exc:
            if want_json:
                return 404, "application/json", json.dumps({"error": str(exc)})
            return 404, HTML, _home(str(exc))
        except Exception as exc:  # noqa: BLE001
            msg = f"Error obteniendo datos: {exc}"
            if want_json:
                return 500, "application/json", json.dumps({"error": msg})
            return 500, HTML, _home(msg)
        if want_json:
            payload = report.to_dict()
            payload["stats"] = _stats_json(stats)
            return 200, "application/json", json.dumps(payload, ensure_ascii=False, default=str)
        return 200, HTML, full_page(render_html(report, stats, with_form=True))
    return 404, "text/plain; charset=utf-8", "Not found"


class Handler(BaseHTTPRequestHandler):
    n_events = DEFAULT_EVENTS

    def do_GET(self):
        code, ctype, body = handle_request(self.path, self.n_events)
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # silencioso salvo errores
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)


def serve(port: int = 8765, n_events: int = DEFAULT_EVENTS, open_browser: bool = True):
    Handler.n_events = n_events
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Servidor en {url}  (Ctrl+C para salir)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
