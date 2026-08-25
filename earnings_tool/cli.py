"""CLI: python -m earnings_tool TICKER [--n 20] [--html out.html] [--json out.json] [--open] [--serve]"""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from rich.console import Console

from .analysis import analyze
from .data import TickerNotFound, fetch_report
from .report_html import full_page, render_html
from .report_terminal import render


def main(argv=None):
    ap = argparse.ArgumentParser(prog="earnings", description="Análisis de earnings de un ticker (últimos N eventos, beat/miss, reacción del precio, analistas y próximo earning).")
    ap.add_argument("ticker", nargs="?", help="Ticker, p.ej. AAPL, NVDA, MSFT")
    ap.add_argument("-n", "--events", type=int, default=20, help="Número de eventos a analizar (por defecto 20)")
    ap.add_argument("--html", metavar="FILE", help="Guardar reporte HTML en FILE")
    ap.add_argument("--json", metavar="FILE", help="Guardar datos + estadísticas en JSON")
    ap.add_argument("--open", action="store_true", help="Abrir el HTML en el navegador (implica --html si no se indica)")
    ap.add_argument("--quiet", action="store_true", help="No imprimir el reporte en terminal")
    ap.add_argument("--no-intraday", action="store_true",
                    help="No descargar velas intradía (sin columna de máximo de la primera vela)")
    ap.add_argument("--no-options", action="store_true",
                    help="No consultar la cadena de opciones (más rápido, sin movimiento implícito)")
    ap.add_argument("--serve", action="store_true", help="Lanzar interfaz web local para elegir ticker")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)

    if args.serve:
        from .server import serve
        serve(port=args.port, n_events=args.events)
        return 0

    if not args.ticker:
        ap.error("indica un ticker o usa --serve")

    console = Console()
    with console.status(f"Descargando datos de {args.ticker.upper()}…"):
        try:
            report = fetch_report(args.ticker, n_events=args.events, with_options=not args.no_options,
                                  with_intraday=not args.no_intraday)
        except TickerNotFound as exc:
            console.print(f"[red]Error:[/] {exc}")
            return 1
    stats = analyze(report)

    if not args.quiet:
        render(report, stats, console)

    html_path = args.html
    if args.open and not html_path:
        html_path = f"{report.ticker}_earnings.html"
    if html_path:
        Path(html_path).write_text(full_page(render_html(report, stats)), encoding="utf-8")
        console.print(f"[green]HTML guardado:[/] {html_path}")
        if args.open:
            webbrowser.open(Path(html_path).resolve().as_uri())

    if args.json:
        payload = report.to_dict()
        st = {k: v for k, v in stats.items() if k not in ("best_surprise", "worst_surprise", "best_move", "worst_move")}
        for k in ("best_surprise", "worst_surprise", "best_move", "worst_move"):
            st[k] = stats[k].__dict__ if stats[k] else None
        payload["stats"] = st
        Path(args.json).write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        console.print(f"[green]JSON guardado:[/] {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
