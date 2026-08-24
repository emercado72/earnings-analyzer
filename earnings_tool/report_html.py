"""Reporte HTML autocontenido (gráficos SVG inline, tema claro/oscuro)."""
from __future__ import annotations

import html
import json

from .data import TickerReport

CSS = """
:root{color-scheme:light;--bg:#fcfcfb;--card:#ffffff;--line:#e6e5e1;--ink:#0b0b0b;--ink2:#52514e;--ink3:#8a8984;
 --pos:#2a78d6;--neg:#e34948;--mid:#f0efec;--good:#0ca30c;--warn:#fab219;--crit:#d03b3b;--grid:#ebeae6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#1a1a19;--card:#232322;--line:#34342f;--ink:#fff;--ink2:#c3c2b7;--ink3:#8f8e86;--pos:#3987e5;--neg:#e66767;--mid:#383835;--grid:#2e2e2b}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#1a1a19;--card:#232322;--line:#34342f;--ink:#fff;--ink2:#c3c2b7;--ink3:#8f8e86;--pos:#3987e5;--neg:#e66767;--mid:#383835;--grid:#2e2e2b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"Segoe UI",Inter,Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:26px;margin:0 0 2px}h2{font-size:17px;margin:0 0 12px;font-weight:600}
.sub{color:var(--ink2);margin-bottom:22px}.sub b{color:var(--ink)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:18px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-bottom:18px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;position:relative;cursor:help;transition:border-color .15s,transform .15s}
.tile[data-tip]:hover,.tile[data-tip]:focus-visible{border-color:var(--pos);transform:translateY(-1px);outline:none}
.tile .k{font-size:12px;color:var(--ink3);text-transform:uppercase;letter-spacing:.04em;padding-right:16px}.tile .v{font-size:22px;font-weight:600;margin-top:2px;white-space:nowrap}.tile .d{font-size:12px;color:var(--ink2)}
.tile .q{position:absolute;top:10px;right:10px;width:15px;height:15px;border-radius:50%;border:1px solid var(--line);color:var(--ink3);font-size:10px;font-weight:700;line-height:13px;text-align:center;opacity:.55}
.tile[data-tip]:hover .q,.tile[data-tip]:focus-visible .q{opacity:1;border-color:var(--pos);color:var(--pos)}
th[data-tip]{cursor:help;text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px;text-decoration-color:var(--ink3)}
.pos{color:var(--pos)}.neg{color:var(--neg)}.meet{color:var(--warn)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:820px){.grid2{grid-template-columns:1fr}}
table{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}th{color:var(--ink2);font-weight:600;font-size:12px}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}.tw{overflow-x:auto}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.03em}
.badge.beat{background:color-mix(in srgb,var(--pos) 15%,transparent);color:var(--pos)}.badge.miss{background:color-mix(in srgb,var(--neg) 15%,transparent);color:var(--neg)}.badge.meet{background:color-mix(in srgb,var(--warn) 22%,transparent);color:var(--ink)}
svg{width:100%;height:auto;display:block}svg text{fill:var(--ink2);font-size:11px}.axis{stroke:var(--ink3);stroke-width:1}.gridl{stroke:var(--grid);stroke-width:1}
.bar{cursor:pointer}.bar:hover{opacity:.75}
.legend{display:flex;gap:16px;font-size:12px;color:var(--ink2);margin-top:6px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
ul.ins{margin:0;padding-left:20px}ul.ins li{margin:5px 0}
.kv{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px;font-size:14px}.kv b{color:var(--ink2);font-weight:500}
.dist{display:flex;height:16px;border-radius:6px;overflow:hidden;gap:2px;margin:6px 0 2px}.dist span{display:block}
.note{font-size:12px;color:var(--ink3);margin-top:14px}
#tip{position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:12.5px;line-height:1.45;box-shadow:0 6px 22px rgba(0,0,0,.18);display:none;z-index:99;color:var(--ink2);max-width:330px}
#tip b{display:block;color:var(--ink);font-size:13px;margin-bottom:3px}#tip em{font-style:normal;color:var(--ink);font-weight:600}
form.search{display:flex;gap:8px;margin-bottom:18px}form.search input{padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font-size:15px;text-transform:uppercase}
form.search button{padding:8px 16px;border-radius:8px;border:1px solid var(--pos);background:var(--pos);color:#fff;font-weight:600;cursor:pointer}
"""


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


def _cls(v):
    return "" if v is None else ("pos" if v > 0 else ("neg" if v < 0 else "meet"))


def _bar_chart(events, attr, title, unit="%"):
    """Gráfico de barras divergente (SVG) cronológico, más antiguo a la izquierda."""
    ev = list(reversed(events))
    vals = [getattr(e, attr) for e in ev]
    W, H, L, R, T, B = 560, 220, 42, 10, 14, 34
    n = max(len(ev), 1)
    vmax = max((abs(v) for v in vals if v is not None), default=1) or 1
    vmax *= 1.15
    ph = H - T - B
    y0 = T + ph / 2
    sy = (ph / 2) / vmax
    slot = (W - L - R) / n
    bw = max(slot - 2, 3)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(title)}">']
    # grid
    step = _nice_step(vmax)
    v = -step * int(vmax // step)
    while v <= vmax:
        y = y0 - v * sy
        parts.append(f'<line class="gridl" x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text x="{L - 6}" y="{y + 4:.1f}" text-anchor="end">{v:+.0f}{unit}</text>')
        v += step
    parts.append(f'<line class="axis" x1="{L}" x2="{W - R}" y1="{y0:.1f}" y2="{y0:.1f}"/>')
    lab_step = max(1, n // 6)
    last_lab = -lab_step
    for i, (e, val) in enumerate(zip(ev, vals)):
        x = L + i * slot + (slot - bw) / 2
        if i % lab_step == 0 or (i == n - 1 and i - last_lab >= lab_step / 2):
            last_lab = i
            parts.append(f'<text x="{x + bw / 2:.1f}" y="{H - 12}" text-anchor="middle">{e.date[:7]}</text>')
        if val is None:
            continue
        h = abs(val) * sy
        y = y0 - h if val >= 0 else y0
        color = "var(--pos)" if val >= 0 else "var(--neg)"
        tip = html.escape(f"{e.date} · {title}: {val:+.2f}{unit} · {e.result.upper()}")
        parts.append(
            f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(h, 1):.1f}" rx="2" '
            f'fill="{color}" data-tip="{tip}"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _nice_step(vmax):
    for s in (0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 500):
        if vmax / s <= 5:
            return s
    return 1000


def _dist_bar(row):
    keys = [("strongBuy", "var(--good)", "Strong Buy"), ("buy", "color-mix(in srgb,var(--good) 55%,transparent)", "Buy"),
            ("hold", "var(--warn)", "Hold"), ("sell", "color-mix(in srgb,var(--crit) 55%,transparent)", "Sell"),
            ("strongSell", "var(--crit)", "Strong Sell")]
    tot = sum(row[k] for k, _, _ in keys) or 1
    spans = "".join(f'<span style="width:{row[k] / tot * 100:.1f}%;background:{c}" title="{lbl}: {row[k]}"></span>'
                    for k, c, lbl in keys if row[k])
    return f'<div class="dist">{spans}</div>'


def render_html(report: TickerReport, stats: dict, with_form: bool = False) -> str:
    s, an, nx, e = stats, report.analysts, report.next_earnings, stats["expectation"]
    cur = html.escape(report.currency)
    esc = html.escape

    rows = []
    for i, ev in enumerate(report.events, 1):
        rows.append(
            f"<tr><td>{i}</td><td>{ev.date} <span style='color:var(--ink3)'>{ev.timing}</span></td>"
            f"<td>{_num(ev.eps_estimate)}</td><td>{_num(ev.eps_reported)}</td>"
            f"<td class='{_cls(ev.surprise_pct)}'>{_pct(ev.surprise_pct)}</td>"
            f"<td><span class='badge {ev.result}'>{ev.result.upper()}</span></td>"
            f"<td>{_num(ev.close_before)}</td><td>{_num(ev.close_after)}</td>"
            f"<td class='{_cls(ev.move_1d_pct)}'>{_pct(ev.move_1d_pct)}</td>"
            f"<td class='{_cls(ev.move_5d_pct)}'>{_pct(ev.move_5d_pct)}</td></tr>"
        )

    up = e.get("target_upside")
    def _t(title, body):
        return html.escape(f"{title}||{body}")

    n_ev = s["n"]
    tiles = [
        ("Tasa de beat", _pct(s["beat_rate"], False, 0), f"{s['beats']} beats · {s['misses']} misses · {s['meets']} meets",
         _t("¿Cuántas veces batió al consenso?",
            f"Antes de cada resultado los analistas estiman un beneficio por acción (EPS). Si el real supera esa estimación es un BEAT; si queda por debajo, un MISS. "
            f"Aquí: {s['beats']} de {n_ev} reportes por encima de lo esperado. Un porcentaje alto indica una empresa predecible o un consenso conservador.")),
        ("Sorpresa media EPS", _pct(s["avg_surprise"]), f"mediana {_pct(s['median_surprise'])}",
         _t("¿Por cuánto margen suele batir?",
            f"No es lo mismo superar el consenso por un 0,5% que por un 20%. Es la diferencia media entre el EPS real y el estimado, en porcentaje. "
            f"Media {_pct(s['avg_surprise'])} y mediana {_pct(s['median_surprise'])}: la mediana ignora los trimestres extremos, así que si ambas se parecen la sorpresa es estable.")),
        ("Movimiento típico 1d", "±" + _pct(s["avg_abs_move"], False), f"sube el {_pct(s['up_rate'], False, 0)} de las veces",
         _t("¿Cuánto sacude la acción?",
            f"Media del movimiento del precio en la primera sesión tras el anuncio, sin mirar la dirección (una subida del 5% y una caída del 5% cuentan igual). "
            f"Mide el tamaño del susto: históricamente ±{_pct(s['avg_abs_move'], False)}, con un máximo de {_pct(s['max_abs_move'], False)}. Es el número que usamos para el rango de precio del próximo earning.")),
        ("Reacción media 1d", _pct(s["avg_move"]), f"5 días: {_pct(s['avg_move_5d'])}",
         _t("¿Con qué signo acaba el día?",
            f"El mismo movimiento pero con signo: al sumar subidas y bajadas, ¿queda a favor o en contra? {_pct(s['avg_move'])} de media. "
            f"Si es mucho menor que el movimiento típico (±{_pct(s['avg_abs_move'], False)}), significa que hay saltos fuertes en ambas direcciones que se cancelan entre sí. A 5 días: {_pct(s['avg_move_5d'])}.")),
        ("Si BEAT / si MISS", f"{_pct(s['avg_move_on_beat'])} / {_pct(s['avg_move_on_miss'])}", f"sube en {_pct(s['up_rate_on_beat'], False, 0)} de los beats",
         _t("¿Premia el mercado el beat?",
            f"La comparación clave: reacción media del precio cuando bate ({_pct(s['avg_move_on_beat'])}) frente a cuando falla ({_pct(s['avg_move_on_miss'])}). "
            f"Solo sube en el {_pct(s['up_rate_on_beat'], False, 0)} de los beats. Si ese porcentaje es bajo, el aprobado ya estaba descontado en el precio y lo que manda es la previsión (guidance) que da la empresa.")),
        ("Consenso analistas", (an.recommendation_key or "—").replace("_", " ").upper(),
         f"{an.n_opinions or '?'} analistas · media {an.recommendation_mean:.2f}/5" if an.recommendation_mean else "",
         _t("¿Qué recomiendan los expertos?",
            f"Recomendación agregada de {an.n_opinions or '?'} analistas que cubren el valor, en una escala de 1 a 5 donde 1 es strong buy y 5 es sell"
            + (f"; aquí {an.recommendation_mean:.2f}." if an.recommendation_mean else ".")
            + " Abajo tienes cómo se reparten los votos y si han cambiado de opinión en los últimos 3 meses. Es opinión de mercado, no una verdad: suele ir sesgada hacia comprar.")),
        ("Precio objetivo medio", f"{_num(an.target_mean)}", (f"<span class='{_cls(up)}'>{_pct(up)}</span> vs {_num(report.price)} {cur}") if up is not None else "",
         _t("¿A cuánto creen que llegará?",
            f"Media de los precios objetivo a 12 meses publicados por los analistas: {_num(an.target_mean)} {cur} frente a {_num(report.price)} {cur} de hoy"
            + (f", es decir un potencial de {_pct(up)}." if up is not None else ".")
            + f" Ojo al rango completo ({_num(an.target_low)}–{_num(an.target_high)}): cuanto más abierto, menos acuerdo hay entre ellos.")),
        ("Próximo earnings", esc(nx.date or "por confirmar"), f"EPS est. {_num(nx.eps_avg)} ({_num(nx.eps_low)}–{_num(nx.eps_high)})",
         _t("El próximo examen",
            f"Fecha prevista del siguiente reporte y la nota que espera el mercado: EPS de {_num(nx.eps_avg)}"
            + (f", un {_pct(nx.eps_growth * 100)} frente a los {_num(nx.eps_year_ago)} del mismo trimestre del año pasado" if nx.eps_growth is not None else "")
            + f". Batir esa cifra es el listón; el rango {_num(nx.eps_low)}–{_num(nx.eps_high)} recoge al analista más pesimista y al más optimista.")),
    ]
    tiles_html = "".join(
        f"<div class='tile' data-tip=\"{tip}\" tabindex='0'><div class='q'>?</div>"
        f"<div class='k'>{k}</div><div class='v'>{v}</div><div class='d'>{d}</div></div>"
        for k, v, d, tip in tiles
    )

    dist_html = ""
    if an.distribution:
        labels = {"0m": "Actual", "-1m": "Hace 1 mes", "-2m": "Hace 2 meses", "-3m": "Hace 3 meses"}
        dist_html = "<table><tr><th>Periodo</th><th style='text-align:left;width:40%'>Distribución</th><th>S.Buy</th><th>Buy</th><th>Hold</th><th>Sell</th><th>S.Sell</th></tr>"
        for r in an.distribution:
            dist_html += (f"<tr><td>{labels.get(r['period'], r['period'])}</td><td style='text-align:left'>{_dist_bar(r)}</td>"
                          f"<td>{r['strongBuy']}</td><td>{r['buy']}</td><td>{r['hold']}</td><td>{r['sell']}</td><td>{r['strongSell']}</td></tr>")
        dist_html += "</table><div class='legend'><span><i style='background:var(--good)'></i>Buy</span><span><i style='background:var(--warn)'></i>Hold</span><span><i style='background:var(--crit)'></i>Sell</span></div>"

    growth = f" · {_pct(nx.eps_growth * 100)} interanual (hace un año {_num(nx.eps_year_ago)})" if nx.eps_growth is not None else ""
    rgrowth = f" · {_pct(nx.rev_growth * 100)} interanual" if nx.rev_growth is not None else ""
    next_html = f"""<div class="kv">
      <b>Fecha</b><span>{esc(nx.date or 'por confirmar')}</span>
      <b>EPS consenso</b><span>{_num(nx.eps_avg)} (rango {_num(nx.eps_low)}–{_num(nx.eps_high)}, {nx.n_analysts or '?'} analistas){growth}</span>
      {"<b>EPS si repite sorpresa mediana</b><span>" + f"{e['eps_adjusted']:.2f}" + "</span>" if e.get('eps_adjusted') is not None else ""}
      <b>Ingresos consenso</b><span>{_big(nx.rev_avg)} (rango {_big(nx.rev_low)}–{_big(nx.rev_high)}){rgrowth}</span>
      {"<b>EPS trimestre siguiente</b><span>" + _num(nx.next_q_eps_avg) + "</span>" if nx.next_q_eps_avg is not None else ""}
      {"<b>EPS año fiscal</b><span>" + _num(nx.fy_eps_avg) + (f" ({_pct(nx.fy_eps_growth * 100)})" if nx.fy_eps_growth is not None else "") + "</span>" if nx.fy_eps_avg is not None else ""}
      {"<b>Rango de precio implícito</b><span>±" + f"{e['typical_move']:.1f}% → {_num(e['price_down'])} – {_num(e['price_up'])} {cur}" + "</span>" if e.get('price_up') is not None else ""}
    </div>"""

    form = ""
    if with_form:
        form = ("<form class='search' action='/report' method='get'><input name='ticker' placeholder='Ticker (p.ej. NVDA)' "
                f"value='{esc(report.ticker)}' required><button>Analizar</button></form>")

    ins = "".join(f"<li>{esc(i)}</li>" for i in s["insights"])
    return f"""<title>{esc(report.ticker)} Earnings</title>
<style>{CSS}</style>
<div class="wrap">
{form}
<h1>{esc(report.name)} <span style="color:var(--ink3);font-weight:400">({esc(report.ticker)})</span></h1>
<div class="sub">{esc(report.exchange or '')} · {esc(report.sector or '')} / {esc(report.industry or '')} · Precio <b>{_num(report.price)} {cur}</b> · Generado {esc(report.generated_at)} · Fuente: Yahoo Finance</div>
<div class="tiles">{tiles_html}</div>
<div class="grid2">
  <div class="card"><h2>Sorpresa de EPS por evento (%)</h2>{_bar_chart(report.events, 'surprise_pct', 'Sorpresa EPS')}
    <div class="legend"><span><i style="background:var(--pos)"></i>Beat</span><span><i style="background:var(--neg)"></i>Miss</span></div></div>
  <div class="card"><h2>Reacción del precio en la sesión post-earnings (%)</h2>{_bar_chart(report.events, 'move_1d_pct', 'Reacción 1d')}
    <div class="legend"><span><i style="background:var(--pos)"></i>Sube</span><span><i style="background:var(--neg)"></i>Baja</span></div></div>
</div>
<div class="card"><h2>Lectura</h2><ul class="ins">{ins}</ul></div>
<div class="grid2">
  <div class="card"><h2>Valoración de analistas</h2>
    <div class="kv"><b>Consenso</b><span><strong>{(an.recommendation_key or '—').replace('_', ' ').upper()}</strong>{f" · nota media {an.recommendation_mean:.2f}/5 (1 = strong buy)" if an.recommendation_mean else ""} · {an.n_opinions or '?'} analistas</span>
    <b>Precio objetivo</b><span>medio {_num(an.target_mean)} · mediana {_num(an.target_median)} · rango {_num(an.target_low)}–{_num(an.target_high)} {cur}{f" · potencial <span class='{_cls(up)}'>{_pct(up)}</span>" if up is not None else ""}</span></div>
    <div style="margin-top:12px">{dist_html}</div></div>
  <div class="card"><h2>Expectativa próximo earnings</h2>{next_html}</div>
</div>
<div class="card"><h2>Últimos {s['n']} earnings ({s['first_date']} → {s['last_date']})</h2>
<div class="tw"><table><thead><tr><th>#</th>
<th data-tip="Fecha del reporte||BMO (before market open) = publicó antes de abrir la bolsa, así que la reacción se ve ese mismo día. AMC (after market close) = publicó tras el cierre, y el mercado reacciona a la sesión siguiente.">Fecha</th>
<th data-tip="EPS estimado||Beneficio por acción que esperaban los analistas para ese trimestre. Es el listón a superar.">EPS est.</th>
<th data-tip="EPS real||Beneficio por acción que la empresa reportó de verdad.">EPS real</th>
<th data-tip="Sorpresa||Diferencia porcentual entre el EPS real y el estimado. Positiva = batió al consenso.">Sorpresa</th>
<th data-tip="Resultado||BEAT si superó el consenso, MISS si quedó por debajo, MEET si acertó en el clavo.">Resultado</th>
<th data-tip="Cierre previo||Precio de cierre de la sesión anterior a que el mercado pudiera reaccionar al reporte. Es la referencia de partida.">Cierre prev.</th>
<th data-tip="Cierre posterior||Precio de cierre de la primera sesión en la que el mercado ya conocía el reporte.">Cierre post</th>
<th data-tip="Reacción a 1 día||Cuánto se movió el precio entre esos dos cierres. Es el veredicto inmediato del mercado sobre el reporte.">Reacción 1d</th>
<th data-tip="Reacción a 5 días||Movimiento acumulado tras cinco sesiones. Sirve para ver si el golpe inicial se mantuvo o se dio la vuelta al reposar la noticia.">5 días</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<div class="note">Beat/miss según EPS reportado vs consenso (Yahoo Finance). Reacción 1d = cierre de la primera sesión tras el anuncio vs cierre previo (BMO: la sesión del mismo día; AMC: la sesión siguiente). Precios ajustados por splits.</div></div>
</div>
<div id="tip"></div>
<script>
(function(){{
  var tip=document.getElementById('tip');
  function show(el,x,y){{
    var raw=el.getAttribute('data-tip')||'';var p=raw.split('||');
    tip.innerHTML=p.length>1?'<b>'+p[0]+'</b>'+p.slice(1).join('||'):p[0];
    tip.style.display='block';tip.style.left='0px';tip.style.top='0px';
    var r=tip.getBoundingClientRect();
    var left=x+14,top=y+16;
    if(left+r.width>window.innerWidth-10)left=Math.max(10,x-r.width-14);
    if(top+r.height>window.innerHeight-10)top=Math.max(10,y-r.height-16);
    tip.style.left=left+'px';tip.style.top=top+'px';
  }}
  function hide(){{tip.style.display='none';}}
  document.querySelectorAll('[data-tip]').forEach(function(el){{
    el.addEventListener('mousemove',function(ev){{show(el,ev.clientX,ev.clientY);}});
    el.addEventListener('mouseleave',hide);
    el.addEventListener('focus',function(){{
      var r=el.getBoundingClientRect();show(el,r.left+r.width/2-14,r.bottom-16);
    }});
    el.addEventListener('blur',hide);
  }});
  document.addEventListener('keydown',function(ev){{if(ev.key==='Escape')hide();}});
  window.addEventListener('scroll',hide,{{passive:true}});
}})();
</script>"""


def full_page(body: str) -> str:
    """Envuelve el fragmento en un documento completo (title/style van al <head>)."""
    i = body.index('<div class="wrap"')
    head, rest = body[:i], body[i:]
    return ("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"{head}</head><body>{rest}</body></html>")
