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
    t.add_column("Apert", justify="right", no_wrap=True)
    t.add_column("Máx día", justify="right", no_wrap=True)
    t.add_column("Máx 1ªvela", justify="right", no_wrap=True)
    t.add_column("P. post", justify="right")
    t.add_column("React 1d", justify="right", no_wrap=True)
    t.add_column("5d", justify="right", no_wrap=True)
    for i, e in enumerate(report.events, 1):
        def _peak(price, pct):
            if price is None:
                return Text("—", style="dim")
            txt = Text(f"{price:,.2f} ")
            txt.append_text(_color_pct(pct))
            return txt
        t.add_row(str(i), e.date, e.timing, _num(e.eps_estimate), _num(e.eps_reported),
                  _color_pct(e.surprise_pct), _result_text(e.result),
                  _num(e.close_before),
                  _peak(e.open_price, e.gap_pct),
                  _peak(e.day_high, e.day_high_pct),
                  _peak(e.oc_high, e.oc_high_pct),
                  _num(e.close_after),
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
    ss = s.get("session") or {}
    if ss.get("avg_day_high") is not None:
        summ.add_row("Máximo medio de la sesión", _pct(ss["avg_day_high"]),
                     "Gap medio de apertura", _pct(ss["avg_gap"]))
    if ss.get("n_oc"):
        iv = "/".join(ss["oc_intervals"])
        summ.add_row(f"Pico medio 1ª vela ({iv})",
                     f"{_pct(ss['avg_oc_high'])} · n={ss['n_oc']}",
                     "Máx. del día en la 1ª vela", _pct(ss["peak_in_oc_rate"], signed=False, nd=0))
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
        p.add_row("Rango por histórico", f"±{e['typical_move']:.1f}% → {_num(e['price_down'])} – {_num(e['price_up'])} {cur}")
    console.print(Panel(p, title="Expectativa próximo earnings", box=box.ROUNDED))

    # ---- movimiento esperado por opciones --------------------------------
    em = getattr(report, "expected_move", None)
    if em is not None:
        if not em.available:
            console.print(Panel(Text(em.reason, style="dim"),
                                title="Movimiento esperado para el día del earning", box=box.ROUNDED))
        else:
            g = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
            g.add_column(style="bold"); g.add_column(); g.add_column(style="bold"); g.add_column()
            g.add_row("Implícito (opciones)", f"[bold cyan]±{_pct(em.implied_move_pct, signed=False)}[/]",
                      "Rango implícito", f"{_num(em.implied_low)} – {_num(em.implied_high)} {cur}")
            pv = em.premium_vs_hist
            verdict = "—" if pv is None else ("prima cara" if pv > 1 else ("prima barata" if pv < -1 else "en línea"))
            g.add_row("Histórico medio", f"±{_pct(em.hist_move_pct, signed=False)}",
                      "Implícito vs histórico", f"{_pct(pv)} ({verdict})")
            g.add_row("Vencimiento", f"{em.expiry} ({em.days_to_expiry} días)",
                      "Straddle ATM", f"{_num(em.atm_strike)} → {_num(em.straddle)} {cur}"
                      + (f" · IV {em.atm_iv * 100:.0f}%" if em.atm_iv else ""))
            if em.hist_inside_rate is not None:
                g.add_row("Se quedó dentro", f"{em.hist_inside_rate:.0f}% de {em.n_hist} earnings",
                          "Percentiles |mov|", f"p50 ±{_pct(s.get('p50_abs_move'), signed=False)} · "
                                               f"p80 ±{_pct(s.get('p80_abs_move'), signed=False)}")
            if not em.covers_earnings:
                g.add_row("Aviso", "[yellow]El vencimiento elegido no cubre la fecha del earning.[/]", "", "")
            console.print(Panel(g, title="Movimiento esperado para el día del earning", box=box.ROUNDED))

            for kind, label in (("call", "Calls (al alza)"), ("put", "Puts (a la baja)")):
                rows = [r for r in em.strikes if r.kind == kind]
                if not rows:
                    continue
                st = Table(title=label, box=box.SIMPLE_HEAVY, header_style="bold", title_justify="left")
                st.add_column("Strike", justify="right"); st.add_column("Dist.", justify="right")
                st.add_column("Prima", justify="right"); st.add_column("Breakeven", justify="right")
                st.add_column("Mov. nec.", justify="right"); st.add_column("Hist. supera BE", justify="right")
                st.add_column("IV", justify="right"); st.add_column("OI", justify="right")
                for r in rows:
                    style = "bold" if abs(r.distance_pct) < 0.75 else ("dim" if not r.inside_implied else "")
                    hb = f"{r.hist_hit_breakeven:.0f}% ({r.hist_hit_n}/{em.n_hist})" if r.hist_hit_breakeven is not None else "—"
                    st.add_row(_num(r.strike), _pct(r.distance_pct), _num(r.premium), _num(r.breakeven),
                               _pct(r.breakeven_pct), hb,
                               f"{r.iv * 100:.0f}%" if r.iv else "—", f"{r.open_interest:,}", style=style)
                console.print(st)
            console.print("[dim]Breakeven = strike ± prima. «Hist. supera BE» = cuántos de los últimos earnings se movieron "
                          "lo suficiente para rebasarlo; es frecuencia pasada, no probabilidad futura.[/]")

    # ---- conclusiones ----------------------------------------------------
    console.print(Panel(Group(*[Text(f"• {i}") for i in s["insights"]]), title="Lectura", box=box.ROUNDED))
    console.print("[dim]Nota: beat/miss según EPS reportado vs consenso de Yahoo Finance. "
                  "Reacción 1d = cierre de la primera sesión tras el anuncio vs cierre previo (BMO: sesión del día; AMC: sesión siguiente).[/]")
