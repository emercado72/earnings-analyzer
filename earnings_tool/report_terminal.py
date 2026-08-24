"""Salida en terminal con rich."""
from __future__ import annotations

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .data import TickerReport


def _pct(v, signed=True, nd=1):
    if v is None:
        return "—"
    return f"{v:+.{nd}f}%" if signed else f"{v:.{nd}f}%"


def _num(v, nd=2):
    return "—" if v is None else f"{v:,.{nd}f}"


def _big(v):
    if v is None:
        return "—"
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(v) >= div:
            return f"{v / div:,.2f}{suf}"
    return f"{v:,.0f}"


def _color_pct(v, nd=1):
    if v is None:
        return Text("—", style="dim")
    style = "green" if v > 0 else ("red" if v < 0 else "yellow")
    return Text(f"{v:+.{nd}f}%", style=style)


def _result_text(r):
    return {"beat": Text("BEAT", style="bold green"), "miss": Text("MISS", style="bold red"),
            "meet": Text("MEET", style="bold yellow")}.get(r, Text("n/d", style="dim"))


def render(report: TickerReport, stats: dict, console: Console | None = None):
    console = console or Console()
    cur = report.currency

    # ---- cabecera --------------------------------------------------------
    head = Text()
    head.append(f"{report.name} ({report.ticker})", style="bold")
    head.append(f"  {report.exchange or ''}  ·  {report.sector or ''} / {report.industry or ''}\n", style="dim")
    head.append(f"Precio: {_num(report.price)} {cur}", style="bold cyan")
    head.append(f"   ·   Generado: {report.generated_at}   ·   Fuente: Yahoo Finance", style="dim")
    console.print(Panel(head, box=box.ROUNDED))

    # ---- tabla de eventos ------------------------------------------------
    t = Table(title=f"Últimos {stats['n']} earnings ({stats['first_date']} → {stats['last_date']})",
              box=box.SIMPLE_HEAVY, header_style="bold")
    t.add_column("#", justify="right", style="dim")
    t.add_column("Fecha", no_wrap=True)
    t.add_column("Hora", justify="center")
    t.add_column("EPS est", justify="right")
    t.add_column("EPS real", justify="right")
    t.add_column("Sorpr.", justify="right", no_wrap=True)
    t.add_column("Result", justify="center")
    t.add_column("P. prev", justify="right")
    t.add_column("P. post", justify="right")
    t.add_column("React 1d", justify="right", no_wrap=True)
    t.add_column("5d", justify="right", no_wrap=True)
    for i, e in enumerate(report.events, 1):
        t.add_row(str(i), e.date, e.timing, _num(e.eps_estimate), _num(e.eps_reported),
                  _color_pct(e.surprise_pct), _result_text(e.result),
                  _num(e.close_before), _num(e.close_after),
                  _color_pct(e.move_1d_pct), _color_pct(e.move_5d_pct))
    console.print(t)

    # ---- resumen ---------------------------------------------------------
    s = stats
    summ = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    summ.add_column(style="bold"); summ.add_column(); summ.add_column(style="bold"); summ.add_column()
    summ.add_row("Beats / Misses / Meets", f"[green]{s['beats']}[/] / [red]{s['misses']}[/] / [yellow]{s['meets']}[/]",
                 "Tasa de beat", _pct(s["beat_rate"], signed=False, nd=0))
    summ.add_row("Sorpresa media", _pct(s["avg_surprise"]), "Sorpresa mediana", _pct(s["median_surprise"]))
    summ.add_row("Mayor sorpresa", f"{_pct(s['best_surprise'].surprise_pct)} ({s['best_surprise'].date})" if s["best_surprise"] else "—",
                 "Peor sorpresa", f"{_pct(s['worst_surprise'].surprise_pct)} ({s['worst_surprise'].date})" if s["worst_surprise"] else "—")
    summ.add_row("Reacción media 1d", _pct(s["avg_move"]), "Movimiento típico (|1d|)", "±" + _pct(s["avg_abs_move"], signed=False))
    summ.add_row("Sube tras earnings", _pct(s["up_rate"], signed=False, nd=0), "Reacción media 5d", _pct(s["avg_move_5d"]))
    summ.add_row("Reacción media si BEAT", _pct(s["avg_move_on_beat"]), "Reacción media si MISS", _pct(s["avg_move_on_miss"]))
    summ.add_row("Mejor reacción", f"{_pct(s['best_move'].move_1d_pct)} ({s['best_move'].date})" if s["best_move"] else "—",
                 "Peor reacción", f"{_pct(s['worst_move'].move_1d_pct)} ({s['worst_move'].date})" if s["worst_move"] else "—")
    streak = f"{s['streak_n']} × {s['streak_kind']}" if s["streak_n"] else "—"
    corr = f"{s['corr_surprise_move']:.2f}" if s["corr_surprise_move"] is not None else "—"
    summ.add_row("Racha actual", streak, "Corr. sorpresa↔reacción", corr)
    l4, l8 = s["last4"], s["last8"]
    summ.add_row("Últimos 4", f"{l4['beats']}B/{l4['misses']}M · sorpresa {_pct(l4['avg_surprise'])} · reacción {_pct(l4['avg_move'])}",
                 "Últimos 8", f"{l8['beats']}B/{l8['misses']}M · sorpresa {_pct(l8['avg_surprise'])} · reacción {_pct(l8['avg_move'])}")
    console.print(Panel(summ, title="Resumen histórico", box=box.ROUNDED))

    # ---- analistas -------------------------------------------------------
    an = report.analysts
    a = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    a.add_column(style="bold"); a.add_column()
    key = (an.recommendation_key or "—").replace("_", " ").upper()
    mean = f" (media {an.recommendation_mean:.2f}/5)" if an.recommendation_mean else ""
    a.add_row("Consenso", f"[bold]{key}[/]{mean} · {an.n_opinions or '?'} analistas")
    up = s["expectation"].get("target_upside")
    a.add_row("Precio objetivo",
              f"medio {_num(an.target_mean)} · mediana {_num(an.target_median)} · rango {_num(an.target_low)}–{_num(an.target_high)} {cur}"
              + (f"  → potencial [{'green' if up >= 0 else 'red'}]{up:+.1f}%[/]" if up is not None else ""))
    if an.distribution:
        d = Table(box=box.SIMPLE_HEAD, header_style="bold", padding=(0, 1))
        for c in ("Periodo", "Strong Buy", "Buy", "Hold", "Sell", "Strong Sell", "Total"):
            d.add_column(c, justify="right" if c != "Periodo" else "left")
        labels = {"0m": "Actual", "-1m": "Hace 1 mes", "-2m": "Hace 2 meses", "-3m": "Hace 3 meses"}
        for row in an.distribution:
            tot = row["strongBuy"] + row["buy"] + row["hold"] + row["sell"] + row["strongSell"]
            d.add_row(labels.get(row["period"], row["period"]), f"[green]{row['strongBuy']}[/]", f"[green]{row['buy']}[/]",
                      f"[yellow]{row['hold']}[/]", f"[red]{row['sell']}[/]", f"[red]{row['strongSell']}[/]", str(tot))
        a.add_row("Distribución", d)
    console.print(Panel(a, title="Valoración de analistas", box=box.ROUNDED))

    # ---- próximo earnings --------------------------------------------------
    nx, e = report.next_earnings, s["expectation"]
    p = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    p.add_column(style="bold"); p.add_column()
    p.add_row("Fecha", nx.date or "por confirmar")
    g = f" · crecimiento {_pct(nx.eps_growth * 100)} vs {_num(nx.eps_year_ago)} hace un año" if nx.eps_growth is not None else ""
    p.add_row("EPS consenso", f"{_num(nx.eps_avg)} (rango {_num(nx.eps_low)}–{_num(nx.eps_high)}, {nx.n_analysts or '?'} analistas){g}")
    if e.get("eps_adjusted") is not None:
        p.add_row("EPS si repite sorpresa mediana", f"{e['eps_adjusted']:.2f}")
    rg = f" · crecimiento {_pct(nx.rev_growth * 100)}" if nx.rev_growth is not None else ""
    p.add_row("Ingresos consenso", f"{_big(nx.rev_avg)} (rango {_big(nx.rev_low)}–{_big(nx.rev_high)}){rg}")
    if nx.next_q_eps_avg is not None:
        p.add_row("EPS trimestre siguiente", _num(nx.next_q_eps_avg))
    if nx.fy_eps_avg is not None:
        fg = f" ({_pct(nx.fy_eps_growth * 100)})" if nx.fy_eps_growth is not None else ""
        p.add_row("EPS año fiscal", f"{_num(nx.fy_eps_avg)}{fg}")
    if e.get("price_up") is not None:
        p.add_row("Movimiento esperado (hist.)", f"±{e['typical_move']:.1f}% → {_num(e['price_down'])} – {_num(e['price_up'])} {cur}")
    console.print(Panel(p, title="Expectativa próximo earnings", box=box.ROUNDED))

    # ---- conclusiones ----------------------------------------------------
    console.print(Panel(Group(*[Text(f"• {i}") for i in s["insights"]]), title="Lectura", box=box.ROUNDED))
    console.print("[dim]Nota: beat/miss según EPS reportado vs consenso de Yahoo Finance. "
                  "Reacción 1d = cierre de la primera sesión tras el anuncio vs cierre previo (BMO: sesión del día; AMC: sesión siguiente).[/]")
