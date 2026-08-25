"""Obtención de datos de earnings, precios y analistas vía yfinance."""
from __future__ import annotations

import datetime as dt
import logging
import math
import warnings
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


class TickerNotFound(Exception):
    pass


def _f(x) -> Optional[float]:
    """Convierte a float o None (NaN -> None)."""
    try:
        if x is None:
            return None
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


@dataclass
class EarningsEvent:
    date: str                      # YYYY-MM-DD
    timing: str                    # BMO (antes de apertura) | AMC (después del cierre) | n/d
    eps_estimate: Optional[float]
    eps_reported: Optional[float]
    surprise_pct: Optional[float]  # (reportado - estimado) / |estimado| * 100
    result: str                    # beat | miss | meet
    close_before: Optional[float]
    close_after: Optional[float]
    move_1d_pct: Optional[float]   # reacción del precio en la primera sesión post-resultado
    move_5d_pct: Optional[float]   # reacción acumulada a 5 sesiones
    reaction_date: Optional[str] = None    # sesión en la que el mercado reacciona
    open_price: Optional[float] = None     # apertura de esa sesión
    gap_pct: Optional[float] = None        # apertura vs cierre previo
    day_high: Optional[float] = None       # máximo de toda la sesión
    day_high_pct: Optional[float] = None
    day_low: Optional[float] = None
    oc_high: Optional[float] = None        # máximo de la PRIMERA vela (09:30)
    oc_high_pct: Optional[float] = None
    oc_close: Optional[float] = None       # cierre de esa primera vela
    oc_interval: Optional[str] = None      # "30m" | "60m"
    oc_time: Optional[str] = None          # hora de apertura de la vela (p.ej. "09:30")


@dataclass
class NextEarnings:
    date: Optional[str]
    eps_avg: Optional[float]
    eps_low: Optional[float]
    eps_high: Optional[float]
    eps_year_ago: Optional[float]
    eps_growth: Optional[float]      # fracción, p.ej. 0.068
    n_analysts: Optional[int]
    rev_avg: Optional[float]
    rev_low: Optional[float]
    rev_high: Optional[float]
    rev_year_ago: Optional[float]
    rev_growth: Optional[float]
    next_q_eps_avg: Optional[float]  # trimestre siguiente al próximo
    fy_eps_avg: Optional[float]      # año fiscal actual
    fy_eps_growth: Optional[float]


@dataclass
class AnalystView:
    recommendation_key: Optional[str]     # strong_buy | buy | hold | underperform | sell
    recommendation_mean: Optional[float]  # 1 = strong buy ... 5 = sell
    n_opinions: Optional[int]
    target_low: Optional[float]
    target_mean: Optional[float]
    target_median: Optional[float]
    target_high: Optional[float]
    distribution: list = field(default_factory=list)  # [{period, strongBuy, buy, hold, sell, strongSell}]


@dataclass
class TickerReport:
    ticker: str
    name: str
    currency: str
    price: Optional[float]
    exchange: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    events: list                 # list[EarningsEvent], más reciente primero
    next_earnings: NextEarnings
    analysts: AnalystView
    generated_at: str
    expected_move: object = None  # ExpectedMove | None (opciones del vencimiento del earning)

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.expected_move is not None and not isinstance(d.get("expected_move"), dict):
            d["expected_move"] = self.expected_move.to_dict()
        return d


# --------------------------------------------------------------------------- #
# Reacción del precio
# --------------------------------------------------------------------------- #
def _price_reaction(closes: pd.Series, day: dt.date, timing: str):
    """Devuelve (close_before, close_after, move_1d, move_5d) alrededor de un earnings.

    BMO: la reacción ocurre en la sesión del propio día -> before = sesión previa, after = ese día.
    AMC: la reacción ocurre en la sesión siguiente   -> before = ese día,       after = siguiente.
    """
    if closes.empty:
        return None, None, None, None
    idx = closes.index
    pos = idx.searchsorted(day)          # primera sesión >= day
    exact = pos < len(idx) and idx[pos] == day

    if timing == "BMO":
        i_after = pos
        i_before = pos - 1
    else:  # AMC o desconocido
        i_before = pos if exact else pos - 1
        i_after = i_before + 1

    if i_before < 0 or i_after >= len(idx):
        return None, None, None, None, None

    cb, ca = float(closes.iloc[i_before]), float(closes.iloc[i_after])
    m1 = (ca / cb - 1) * 100 if cb else None
    i5 = i_after + 4
    m5 = (float(closes.iloc[i5]) / cb - 1) * 100 if i5 < len(idx) and cb else None
    return cb, ca, m1, m5, idx[i_after]


def _fetch_intraday(t) -> dict:
    """Descarga barras intradía y las indexa por (fecha de sesión, intervalo).

    Yahoo solo sirve intradía reciente: ~60 días para 30m y ~730 para 60m. Los
    earnings anteriores a esa ventana no tienen vela de apertura recuperable.
    """
    out: dict[str, pd.DataFrame] = {}
    for interval, period in (("30m", "60d"), ("60m", "730d")):
        try:
            h = t.history(period=period, interval=interval)
        except Exception:
            continue
        if h is None or h.empty:
            continue
        h = h.copy()
        h["_d"] = [ts.date() for ts in h.index]
        h["_t"] = [ts.strftime("%H:%M") for ts in h.index]
        out[interval] = h
    return out


def _opening_candle(intraday: dict, day: dt.date, day_low, day_high):
    """Primera vela de la sesión `day`. Prefiere 30m; si no, 60m.

    Descarta el dato si no encaja en el rango diario (protege frente a
    desajustes de ajuste por splits entre series diaria e intradía).
    """
    for interval in ("30m", "60m"):
        h = intraday.get(interval)
        if h is None or h.empty:
            continue
        sub = h[h["_d"] == day]
        if sub.empty:
            continue
        bar = sub.iloc[0]
        hi, cl = _f(bar.get("High")), _f(bar.get("Close"))
        if hi is None:
            continue
        if day_low is not None and day_high is not None:
            if not (day_low * 0.98 <= hi <= day_high * 1.02):
                continue  # escalas incoherentes: mejor no mostrar nada
        return hi, cl, interval, str(bar.get("_t"))
    return None, None, None, None


def _timing_from_ts(ts) -> str:
    try:
        h = ts.hour
    except AttributeError:
        return "n/d"
    if h == 0:
        return "n/d"
    return "BMO" if h < 12 else "AMC"


# --------------------------------------------------------------------------- #
# Carga principal
# --------------------------------------------------------------------------- #
def fetch_report(ticker: str, n_events: int = 20, with_options: bool = True,
                 with_intraday: bool = True) -> TickerReport:
    ticker = ticker.strip().upper()
    t = yf.Ticker(ticker)

    try:
        info: dict[str, Any] = t.info or {}
    except Exception:
        info = {}
    if not info or info.get("quoteType") in (None, "NONE") and not info.get("shortName"):
        raise TickerNotFound(f"No se encontró el ticker '{ticker}' en Yahoo Finance.")

    # --- historial de earnings -------------------------------------------
    try:
        ed = t.get_earnings_dates(limit=n_events + 8)
    except Exception as exc:
        raise TickerNotFound(f"Sin datos de earnings para '{ticker}': {exc}")
    if ed is None or ed.empty:
        raise TickerNotFound(f"Yahoo no publica historial de earnings para '{ticker}'.")

    ed = ed.copy()
    ed.columns = [c.strip() for c in ed.columns]
    reported = ed[ed["Reported EPS"].notna()].sort_index(ascending=False).head(n_events)
    upcoming = ed[ed["Reported EPS"].isna()].sort_index(ascending=True)

    # --- precios para medir la reacción ----------------------------------
    if not reported.empty:
        first = reported.index.min().date() - dt.timedelta(days=10)
        try:
            # auto_adjust=False -> precios tal como se vieron en pantalla (con splits
            # aplicados igualmente), en la misma escala que las barras intradía.
            hist = t.history(start=first.isoformat(), auto_adjust=False)
        except Exception:
            hist = pd.DataFrame()
    else:
        hist = pd.DataFrame()
    closes = pd.Series(dtype=float)
    ohlc = pd.DataFrame()
    if not hist.empty:
        ohlc = hist.copy()
        ohlc.index = pd.Index([ts.date() for ts in ohlc.index])
        ohlc = ohlc[~ohlc.index.duplicated(keep="last")].sort_index()
        closes = ohlc["Close"].copy()

    intraday = _fetch_intraday(t) if (with_intraday and not ohlc.empty) else {}

    events: list[EarningsEvent] = []
    for ts, row in reported.iterrows():
        est, rep = _f(row.get("EPS Estimate")), _f(row.get("Reported EPS"))
        sur = _f(row.get("Surprise(%)"))
        if sur is None and est not in (None, 0) and rep is not None:
            sur = (rep - est) / abs(est) * 100
        if sur is None:
            result = "n/d"
        elif sur > 0.05:
            result = "beat"
        elif sur < -0.05:
            result = "miss"
        else:
            result = "meet"
        timing = _timing_from_ts(ts)
        cb, ca, m1, m5, rday = _price_reaction(closes, ts.date(), timing)

        op = gap = dhigh = dhigh_pct = dlow = None
        oc_hi = oc_cl = oc_iv = oc_tm = oc_pct = None
        if rday is not None and rday in ohlc.index:
            row = ohlc.loc[rday]
            op, dhigh, dlow = _f(row.get("Open")), _f(row.get("High")), _f(row.get("Low"))
            if cb:
                gap = (op / cb - 1) * 100 if op else None
                dhigh_pct = (dhigh / cb - 1) * 100 if dhigh else None
            oc_hi, oc_cl, oc_iv, oc_tm = _opening_candle(intraday, rday, dlow, dhigh)
            if oc_hi and cb:
                oc_pct = (oc_hi / cb - 1) * 100

        events.append(EarningsEvent(
            date=ts.date().isoformat(), timing=timing,
            eps_estimate=est, eps_reported=rep, surprise_pct=sur, result=result,
            close_before=cb, close_after=ca, move_1d_pct=m1, move_5d_pct=m5,
            reaction_date=rday.isoformat() if rday is not None else None,
            open_price=op, gap_pct=gap, day_high=dhigh, day_high_pct=dhigh_pct, day_low=dlow,
            oc_high=oc_hi, oc_high_pct=oc_pct, oc_close=oc_cl,
            oc_interval=oc_iv, oc_time=oc_tm,
        ))

    # --- próximo earnings -------------------------------------------------
    cal = {}
    try:
        cal = t.calendar or {}
    except Exception:
        pass
    next_date = None
    if cal.get("Earnings Date"):
        d = cal["Earnings Date"]
        d = d[0] if isinstance(d, (list, tuple)) else d
        next_date = d.isoformat() if hasattr(d, "isoformat") else str(d)
    elif not upcoming.empty:
        next_date = upcoming.index[0].date().isoformat()

    ee = rev = None
    try:
        ee = t.earnings_estimate
    except Exception:
        pass
    try:
        rev = t.revenue_estimate
    except Exception:
        pass

    def _row(df, key):
        if df is None or df.empty or key not in df.index:
            return {}
        return df.loc[key].to_dict()

    q0, q1, y0 = _row(ee, "0q"), _row(ee, "+1q"), _row(ee, "0y")
    r0 = _row(rev, "0q")
    n_an = q0.get("numberOfAnalysts")
    next_earnings = NextEarnings(
        date=next_date,
        eps_avg=_f(q0.get("avg")) or _f(cal.get("Earnings Average")),
        eps_low=_f(q0.get("low")) or _f(cal.get("Earnings Low")),
        eps_high=_f(q0.get("high")) or _f(cal.get("Earnings High")),
        eps_year_ago=_f(q0.get("yearAgoEps")),
        eps_growth=_f(q0.get("growth")),
        n_analysts=int(n_an) if _f(n_an) is not None else None,
        rev_avg=_f(r0.get("avg")) or _f(cal.get("Revenue Average")),
        rev_low=_f(r0.get("low")) or _f(cal.get("Revenue Low")),
        rev_high=_f(r0.get("high")) or _f(cal.get("Revenue High")),
        rev_year_ago=_f(r0.get("yearAgoRevenue")),
        rev_growth=_f(r0.get("growth")),
        next_q_eps_avg=_f(q1.get("avg")),
        fy_eps_avg=_f(y0.get("avg")),
        fy_eps_growth=_f(y0.get("growth")),
    )

    # --- analistas ---------------------------------------------------------
    targets = {}
    try:
        targets = t.analyst_price_targets or {}
    except Exception:
        pass
    dist = []
    try:
        rs = t.recommendations_summary
        if rs is not None and not rs.empty:
            for _, r in rs.iterrows():
                dist.append({
                    "period": str(r.get("period")),
                    "strongBuy": int(r.get("strongBuy", 0) or 0),
                    "buy": int(r.get("buy", 0) or 0),
                    "hold": int(r.get("hold", 0) or 0),
                    "sell": int(r.get("sell", 0) or 0),
                    "strongSell": int(r.get("strongSell", 0) or 0),
                })
    except Exception:
        pass
    analysts = AnalystView(
        recommendation_key=info.get("recommendationKey"),
        recommendation_mean=_f(info.get("recommendationMean")),
        n_opinions=info.get("numberOfAnalystOpinions"),
        target_low=_f(targets.get("low")) or _f(info.get("targetLowPrice")),
        target_mean=_f(targets.get("mean")) or _f(info.get("targetMeanPrice")),
        target_median=_f(targets.get("median")) or _f(info.get("targetMedianPrice")),
        target_high=_f(targets.get("high")) or _f(info.get("targetHighPrice")),
        distribution=dist,
    )

    price = _f(info.get("currentPrice")) or _f(info.get("regularMarketPrice")) or _f(targets.get("current"))
    if price is None and not closes.empty:
        price = float(closes.iloc[-1])

    # --- movimiento implícito por opciones (vencimiento que cubre el earning) ---
    expected_move = None
    if with_options:
        try:
            from .options import fetch_expected_move
            expected_move = fetch_expected_move(
                ticker, next_date, price,
                [e.move_1d_pct for e in events if e.move_1d_pct is not None],
            )
        except Exception as exc:  # noqa: BLE001
            from .options import ExpectedMove
            expected_move = ExpectedMove(False, f"Error leyendo opciones: {exc}")

    return TickerReport(
        ticker=ticker,
        name=info.get("shortName") or info.get("longName") or ticker,
        currency=info.get("currency") or "USD",
        price=price,
        exchange=info.get("fullExchangeName") or info.get("exchange"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        events=events,
        next_earnings=next_earnings,
        analysts=analysts,
        generated_at=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        expected_move=expected_move,
    )
