"""Estadísticas sobre el historial de earnings y expectativa del próximo evento."""
from __future__ import annotations

import statistics
from typing import Optional

from .data import EarningsEvent, TickerReport


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None


def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _pearson(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    xs, ys = zip(*pairs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sxx * syy) ** 0.5


def _pctile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    i = (len(xs) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def _streak(events: list[EarningsEvent]):
    """Racha actual (más reciente primero): ('beat'|'miss'|'meet', n)."""
    if not events or events[0].result == "n/d":
        return None, 0
    kind, n = events[0].result, 0
    for e in events:
        if e.result != kind:
            break
        n += 1
    return kind, n


def _rescue_rate(ev):
    """% de earnings que cerraron abajo pero llegaron a cotizar por encima del cierre previo."""
    red = [e for e in ev if e.move_1d_pct is not None and e.move_1d_pct < 0 and e.day_high_pct is not None]
    if not red:
        return None
    return sum(1 for e in red if e.day_high_pct > 0) / len(red) * 100


def _window(events: list[EarningsEvent], n: int) -> dict:
    ev = [e for e in events[:n] if e.result != "n/d"]
    beats = sum(e.result == "beat" for e in ev)
    misses = sum(e.result == "miss" for e in ev)
    meets = sum(e.result == "meet" for e in ev)
    moves = [e.move_1d_pct for e in ev if e.move_1d_pct is not None]
    return {
        "n": len(ev),
        "beats": beats, "misses": misses, "meets": meets,
        "beat_rate": beats / len(ev) * 100 if ev else None,
        "avg_surprise": _mean([e.surprise_pct for e in ev]),
        "avg_move": _mean(moves),
        "avg_abs_move": _mean([abs(m) for m in moves]),
        "up_rate": sum(m > 0 for m in moves) / len(moves) * 100 if moves else None,
    }


def analyze(report: TickerReport) -> dict:
    ev = [e for e in report.events if e.result != "n/d"]
    n = len(ev)
    beats = [e for e in ev if e.result == "beat"]
    misses = [e for e in ev if e.result == "miss"]
    meets = [e for e in ev if e.result == "meet"]

    moves = [e.move_1d_pct for e in ev if e.move_1d_pct is not None]
    moves5 = [e.move_5d_pct for e in ev if e.move_5d_pct is not None]
    surprises = [e.surprise_pct for e in ev if e.surprise_pct is not None]

    best_sur = max(ev, key=lambda e: e.surprise_pct or -1e9) if surprises else None
    worst_sur = min(ev, key=lambda e: e.surprise_pct or 1e9) if surprises else None
    with_move = [e for e in ev if e.move_1d_pct is not None]
    best_move = max(with_move, key=lambda e: e.move_1d_pct) if with_move else None
    worst_move = min(with_move, key=lambda e: e.move_1d_pct) if with_move else None

    streak_kind, streak_n = _streak(ev)

    beat_moves = [e.move_1d_pct for e in beats if e.move_1d_pct is not None]
    miss_moves = [e.move_1d_pct for e in misses if e.move_1d_pct is not None]

    stats = {
        "n": n,
        "beats": len(beats), "misses": len(misses), "meets": len(meets),
        "beat_rate": len(beats) / n * 100 if n else None,
        "miss_rate": len(misses) / n * 100 if n else None,
        "avg_surprise": _mean(surprises),
        "median_surprise": _median(surprises),
        "best_surprise": best_sur,
        "worst_surprise": worst_sur,
        "avg_move": _mean(moves),
        "median_move": _median(moves),
        "avg_abs_move": _mean([abs(m) for m in moves]),          # "movimiento típico"
        "max_abs_move": max((abs(m) for m in moves), default=None),
        "avg_move_5d": _mean(moves5),
        "p50_abs_move": _pctile([abs(m) for m in moves], 0.50),
        "p80_abs_move": _pctile([abs(m) for m in moves], 0.80),
        "p90_abs_move": _pctile([abs(m) for m in moves], 0.90),
        "up_rate": sum(m > 0 for m in moves) / len(moves) * 100 if moves else None,
        "avg_move_on_beat": _mean(beat_moves),
        "avg_move_on_miss": _mean(miss_moves),
        "up_rate_on_beat": sum(m > 0 for m in beat_moves) / len(beat_moves) * 100 if beat_moves else None,
        "down_rate_on_miss": sum(m < 0 for m in miss_moves) / len(miss_moves) * 100 if miss_moves else None,
        "best_move": best_move,
        "worst_move": worst_move,
        "corr_surprise_move": _pearson([e.surprise_pct for e in ev], [e.move_1d_pct for e in ev]),
        "streak_kind": streak_kind, "streak_n": streak_n,
        "last4": _window(ev, 4),
        "last8": _window(ev, 8),
        "first_date": ev[-1].date if ev else None,
        "last_date": ev[0].date if ev else None,
    }
    # --- comportamiento de la sesión de reacción (apertura / vela 09:30 / máximo) ---
    gaps = [e.gap_pct for e in ev if e.gap_pct is not None]
    dhs = [e.day_high_pct for e in ev if e.day_high_pct is not None]
    oc = [e for e in ev if e.oc_high_pct is not None]
    ocs = [e.oc_high_pct for e in oc]
    # ¿el máximo del día se hizo dentro de la primera vela?
    peak_in_oc = [e for e in oc if e.day_high and e.oc_high and e.oc_high >= e.day_high * 0.999]
    # cuánto del recorrido máximo del día capturaba quien vendía en la primera vela
    # cuánto se quedó el pico de la 1ª vela por debajo del máximo del día (puntos porcentuales)
    shortfall = [
        (e.day_high_pct - e.oc_high_pct)
        for e in oc if e.day_high_pct is not None and e.oc_high_pct is not None
    ]
    stats["session"] = {
        "n_gap": len(gaps),
        "avg_gap": _mean(gaps),
        "avg_day_high": _mean(dhs),
        "n_oc": len(oc),
        "oc_intervals": sorted({e.oc_interval for e in oc if e.oc_interval}),
        "avg_oc_high": _mean(ocs),
        "median_oc_high": _median(ocs),
        "max_oc_high": max(ocs) if ocs else None,
        "min_oc_high": min(ocs) if ocs else None,
        "oc_positive_rate": (sum(1 for x in ocs if x > 0) / len(ocs) * 100) if ocs else None,
        "peak_in_oc_rate": (len(peak_in_oc) / len(oc) * 100) if oc else None,
        "avg_shortfall": _mean(shortfall),
        # cuánto se desinfla el precio desde el máximo de la sesión hasta el cierre
        "avg_fade": _mean([
            e.day_high_pct - e.move_1d_pct
            for e in ev if e.day_high_pct is not None and e.move_1d_pct is not None
        ]),
        # ¿hubo en algún momento de la sesión una ventana en verde para vender?
        "green_window_rate": (sum(1 for x in dhs if x > 0) / len(dhs) * 100) if dhs else None,
        # de los earnings que cerraron en rojo, cuántos tuvieron máximo positivo
        "red_close_green_high": _rescue_rate(ev),
    }
    stats["expectation"] = _expectation(report, stats)
    stats["insights"] = _insights(report, stats)
    return stats


def _expectation(report: TickerReport, s: dict) -> dict:
    """Expectativa para el próximo earnings: rango de precio implícito por el histórico."""
    nx, an = report.next_earnings, report.analysts
    price = report.price
    typ = s.get("avg_abs_move")
    em = getattr(report, "expected_move", None)
    exp = {
        "date": nx.date,
        "eps_avg": nx.eps_avg, "eps_low": nx.eps_low, "eps_high": nx.eps_high,
        "eps_year_ago": nx.eps_year_ago, "eps_growth": nx.eps_growth,
        "rev_avg": nx.rev_avg, "rev_growth": nx.rev_growth,
        "n_analysts": nx.n_analysts,
        "typical_move": typ,
        "price": price,
        "price_up": price * (1 + typ / 100) if price and typ is not None else None,
        "price_down": price * (1 - typ / 100) if price and typ is not None else None,
        "target_upside": (an.target_mean / price - 1) * 100 if price and an.target_mean else None,
    }
    # rango implícito por opciones: es lo que el mercado paga HOY por el evento
    if em is not None and getattr(em, "available", False):
        exp["implied_move"] = em.implied_move_pct
        exp["implied_low"] = em.implied_low
        exp["implied_high"] = em.implied_high
        exp["implied_expiry"] = em.expiry
        exp["premium_vs_hist"] = em.premium_vs_hist
    # EPS "esperado" ajustado por la sorpresa media histórica (heurística)
    if nx.eps_avg is not None and s.get("median_surprise") is not None:
        exp["eps_adjusted"] = nx.eps_avg * (1 + s["median_surprise"] / 100)
    else:
        exp["eps_adjusted"] = None
    return exp


def _insights(report: TickerReport, s: dict) -> list[str]:
    out = []
    if not s["n"]:
        return ["Sin eventos de earnings con EPS reportado."]

    br = s["beat_rate"]
    if br >= 85:
        out.append(f"Historial muy consistente: supera el consenso en el {br:.0f}% de los últimos {s['n']} reportes.")
    elif br >= 65:
        out.append(f"Supera el consenso en el {br:.0f}% de los últimos {s['n']} reportes.")
    elif br >= 45:
        out.append(f"Historial mixto: {s['beats']} beats vs {s['misses']} misses en {s['n']} reportes.")
    else:
        out.append(f"Historial débil: falla el consenso en {s['misses']} de {s['n']} reportes.")

    if s["streak_n"] >= 3:
        word = "beats" if s["streak_kind"] == "beat" else ("misses" if s["streak_kind"] == "miss" else "en línea")
        out.append(f"Racha actual: {s['streak_n']} {word} consecutivos.")

    l8, l4 = s["last8"], s["last4"]
    if l8["beat_rate"] is not None and br is not None and s["n"] >= 12:
        diff = l8["beat_rate"] - br
        if diff >= 15:
            out.append("Tendencia reciente mejora: la tasa de beats de los últimos 8 supera al promedio histórico.")
        elif diff <= -15:
            out.append("Tendencia reciente empeora: la tasa de beats de los últimos 8 está por debajo del promedio histórico.")

    if s["avg_surprise"] is not None:
        out.append(f"Sorpresa media de EPS: {s['avg_surprise']:+.1f}% (mediana {s['median_surprise']:+.1f}%).")

    if s["avg_abs_move"] is not None:
        out.append(
            f"Movimiento típico del precio en la sesión post-earnings: ±{s['avg_abs_move']:.1f}% "
            f"(máximo {s['max_abs_move']:.1f}%); sube en el {s['up_rate']:.0f}% de los casos."
        )
    if s["avg_move_on_beat"] is not None and s["up_rate_on_beat"] is not None:
        out.append(
            f"Tras un beat el precio se mueve {s['avg_move_on_beat']:+.1f}% de media "
            f"y sube en el {s['up_rate_on_beat']:.0f}% de los beats."
        )
        if s["up_rate_on_beat"] < 50:
            out.append("Ojo: superar el consenso NO ha garantizado subida; el mercado suele exigir más que el beat (guidance, márgenes).")
    if s["avg_move_on_miss"] is not None:
        out.append(f"Tras un miss el precio se mueve {s['avg_move_on_miss']:+.1f}% de media "
                   f"({s['misses']} {'caso' if s['misses'] == 1 else 'casos'}).")

    c = s["corr_surprise_move"]
    if c is not None:
        if c >= 0.4:
            out.append(f"La magnitud de la sorpresa explica bien la reacción (correlación {c:.2f}).")
        elif c <= 0.1:
            out.append(f"La reacción del precio apenas depende de la sorpresa de EPS (correlación {c:.2f}); pesan otros factores.")

    ss = s.get("session") or {}
    if ss.get("n_oc"):
        iv = "/".join(ss["oc_intervals"]) or "intradía"
        out.append(
            f"Vela de apertura ({iv}): el pico medio de la primera vela fue {ss['avg_oc_high']:+.1f}% sobre el cierre previo "
            f"(mediana {ss['median_oc_high']:+.1f}%, mejor {ss['max_oc_high']:+.1f}%, peor {ss['min_oc_high']:+.1f}%), "
            f"medido en {ss['n_oc']} de {s['n']} earnings — Yahoo solo guarda intradía reciente."
        )
        if ss.get("peak_in_oc_rate") is not None:
            out.append(
                f"En el {ss['peak_in_oc_rate']:.0f}% de esos casos el MÁXIMO de toda la sesión se hizo dentro de la primera vela: "
                + ("vender ahí capturaba prácticamente el techo del día."
                   if ss["peak_in_oc_rate"] >= 60 else
                   "a menudo el techo del día llegó más tarde, no en la apertura.")
            )
        if ss.get("avg_shortfall") is not None:
            out.append(
                f"El pico de la primera vela se quedó de media {ss['avg_shortfall']:.2f} puntos porcentuales por debajo "
                f"del máximo de toda la sesión."
            )
    if ss.get("avg_fade") is not None:
        out.append(
            f"Del máximo de la sesión al cierre se desinflan de media {ss['avg_fade']:.1f} puntos porcentuales: "
            f"ese es el coste de aguantar hasta el cierre en vez de vender en el pico."
        )
    if ss.get("green_window_rate") is not None:
        out.append(
            f"En el {ss['green_window_rate']:.0f}% de los earnings el precio llegó a cotizar por encima del cierre previo "
            f"en algún momento de la sesión."
        )
    if ss.get("red_close_green_high") is not None:
        out.append(
            f"De los earnings que acabaron cerrando en rojo, el {ss['red_close_green_high']:.0f}% había estado en verde "
            f"durante la sesión: hubo ventana de salida antes del desplome."
        )
    if ss.get("avg_gap") is not None:
        out.append(
            f"Apertura media de la sesión de reacción: {ss['avg_gap']:+.1f}% de gap sobre el cierre previo; "
            f"el máximo del día promedió {ss['avg_day_high']:+.1f}%."
        )

    em = getattr(report, "expected_move", None)
    if em is not None and getattr(em, "available", False):
        out.append(
            f"El mercado de opciones paga un movimiento de ±{em.implied_move_pct:.1f}% para el vencimiento "
            f"{em.expiry} (el que cubre el earning): rango {em.implied_low:,.2f}–{em.implied_high:,.2f}."
        )
        if em.premium_vs_hist is not None:
            if em.premium_vs_hist > 1:
                out.append(
                    f"Las opciones descuentan {em.premium_vs_hist:+.1f} puntos MÁS de lo que se ha movido de media "
                    f"(±{em.hist_move_pct:.1f}% histórico): la prima del evento está cara frente al historial."
                )
            elif em.premium_vs_hist < -1:
                out.append(
                    f"Las opciones descuentan {abs(em.premium_vs_hist):.1f} puntos MENOS que el movimiento medio histórico "
                    f"(±{em.hist_move_pct:.1f}%): la prima del evento está barata frente al historial."
                )
            else:
                out.append(
                    f"El implícito (±{em.implied_move_pct:.1f}%) está en línea con el movimiento medio histórico "
                    f"(±{em.hist_move_pct:.1f}%)."
                )
        if em.hist_inside_rate is not None:
            out.append(
                f"De los últimos {em.n_hist} earnings, el {em.hist_inside_rate:.0f}% se quedó DENTRO de un rango como el "
                f"que hoy pagan las opciones; el {100 - em.hist_inside_rate:.0f}% lo rebasó."
            )
        if s.get("p80_abs_move") is not None:
            out.append(
                f"Percentiles del movimiento histórico: la mitad de los earnings se movió menos de "
                f"±{s['p50_abs_move']:.1f}%, y 8 de cada 10 menos de ±{s['p80_abs_move']:.1f}%."
            )

    an, nx, e = report.analysts, report.next_earnings, s["expectation"]
    if an.recommendation_key:
        key = an.recommendation_key.replace("_", " ")
        mean_txt = f" (nota media {an.recommendation_mean:.2f}/5, 1 = strong buy)" if an.recommendation_mean else ""
        out.append(f"Consenso de analistas: {key.upper()}{mean_txt} con {an.n_opinions or '?'} opiniones.")
    if e.get("target_upside") is not None:
        out.append(
            f"Referencia a 12 meses (no para el día del earning): precio objetivo medio {an.target_mean:,.2f} "
            f"{report.currency}, {e['target_upside']:+.1f}% frente al precio actual ({report.price:,.2f})."
        )
    if nx.eps_avg is not None:
        g = f", {nx.eps_growth * 100:+.1f}% interanual" if nx.eps_growth is not None else ""
        out.append(
            f"Próximo earnings {nx.date or 'fecha por confirmar'}: consenso EPS {nx.eps_avg:.2f} "
            f"(rango {nx.eps_low:.2f}–{nx.eps_high:.2f}{g})."
        )
        if e.get("eps_adjusted") is not None and s["beat_rate"] is not None and s["beat_rate"] >= 65:
            out.append(
                f"Si repite su sorpresa mediana, el EPS reportado rondaría {e['eps_adjusted']:.2f}."
            )
    if e.get("price_up") is not None:
        out.append(
            f"Rango proyectado solo con el histórico (sin opciones): "
            f"{e['price_down']:,.2f} – {e['price_up']:,.2f} {report.currency}."
        )
    return out
