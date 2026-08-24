"""Movimiento implícito por opciones para el día del earning y escalera de strikes.

El "movimiento esperado" (expected move) es lo que el mercado de opciones está
pagando por el evento: el straddle ATM (call + put del mismo strike) del primer
vencimiento que cubre la fecha del reporte, dividido entre el precio spot.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
import warnings
from dataclasses import asdict, dataclass, field
from typing import Optional

import yfinance as yf

warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def _f(x) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        return None if (math.isnan(v) or math.isinf(v)) else v
    except (TypeError, ValueError):
        return None


def _mid(row) -> Optional[float]:
    """Precio medio bid/ask; si no hay horquilla usable, último negociado."""
    b, a = _f(getattr(row, "bid", None)), _f(getattr(row, "ask", None))
    if b is not None and a is not None and b > 0 and a >= b:
        return (b + a) / 2
    last = _f(getattr(row, "lastPrice", None))
    return last if last and last > 0 else None


@dataclass
class StrikeRow:
    kind: str                  # call | put
    strike: float
    distance_pct: float        # distancia del strike al spot, %
    premium: Optional[float]
    breakeven: Optional[float]
    breakeven_pct: Optional[float]   # movimiento necesario para no perder, %
    hist_hit_strike: Optional[float]  # % de earnings pasados que alcanzaron el strike
    hist_hit_breakeven: Optional[float]  # % que superaron el breakeven
    hist_hit_n: int            # nº de earnings históricos que superaron el breakeven
    iv: Optional[float]
    open_interest: Optional[int]
    volume: Optional[int]
    inside_implied: bool       # ¿el strike cae dentro del rango implícito?


@dataclass
class ExpectedMove:
    available: bool
    reason: str = ""
    expiry: Optional[str] = None
    days_to_expiry: Optional[int] = None
    covers_earnings: bool = False
    spot: Optional[float] = None
    atm_strike: Optional[float] = None
    call_mid: Optional[float] = None
    put_mid: Optional[float] = None
    straddle: Optional[float] = None
    implied_move_pct: Optional[float] = None
    implied_low: Optional[float] = None
    implied_high: Optional[float] = None
    atm_iv: Optional[float] = None
    hist_move_pct: Optional[float] = None     # movimiento absoluto medio histórico
    premium_vs_hist: Optional[float] = None   # implícito - histórico (puntos porcentuales)
    hist_inside_rate: Optional[float] = None  # % de earnings que se quedaron dentro del rango implícito
    n_hist: int = 0
    strikes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _pick_expiry(expiries: list[str], earnings_date: Optional[str], today: dt.date):
    """Primer vencimiento en o después del earning (o el más cercano si no hay fecha)."""
    dates = []
    for e in expiries:
        try:
            dates.append(dt.date.fromisoformat(e))
        except ValueError:
            continue
    dates = sorted(d for d in dates if d >= today)
    if not dates:
        return None, False
    if earnings_date:
        try:
            ed = dt.date.fromisoformat(earnings_date)
        except ValueError:
            ed = None
        if ed:
            after = [d for d in dates if d >= ed]
            if after:
                return after[0], True
            # el earning cae más allá del último vencimiento publicado
            return dates[-1], False
    return dates[0], False


def fetch_expected_move(
    ticker: str,
    earnings_date: Optional[str],
    spot: Optional[float],
    hist_moves: Optional[list[float]] = None,
    max_strikes: int = 7,
) -> ExpectedMove:
    """Calcula el movimiento implícito y la escalera de strikes del vencimiento del earning.

    `hist_moves` son las reacciones a 1 día de los earnings pasados (en %), que se
    usan para estimar con qué frecuencia el precio alcanzó históricamente cada strike.
    """
    hist = [m for m in (hist_moves or []) if m is not None]
    t = yf.Ticker(ticker)

    try:
        expiries = list(t.options or [])
    except Exception as exc:  # noqa: BLE001
        return ExpectedMove(False, f"No se pudo leer la cadena de opciones: {exc}")
    if not expiries:
        return ExpectedMove(False, "Este valor no tiene opciones listadas en Yahoo Finance.")

    today = dt.date.today()
    exp, covers = _pick_expiry(expiries, earnings_date, today)
    if exp is None:
        return ExpectedMove(False, "No hay vencimientos futuros disponibles.")

    try:
        chain = t.option_chain(exp.isoformat())
    except Exception as exc:  # noqa: BLE001
        return ExpectedMove(False, f"No se pudo leer el vencimiento {exp}: {exc}")

    calls, puts = chain.calls, chain.puts
    if calls is None or puts is None or calls.empty or puts.empty:
        return ExpectedMove(False, f"El vencimiento {exp} no tiene cotizaciones.")

    if spot is None:
        spot = _f(t.info.get("currentPrice")) or _f(t.info.get("regularMarketPrice"))
    if not spot:
        return ExpectedMove(False, "Sin precio spot para calcular el movimiento implícito.")

    common = sorted(set(calls.strike) & set(puts.strike))
    if not common:
        return ExpectedMove(False, f"El vencimiento {exp} no tiene strikes comunes en calls y puts.")
    atm = min(common, key=lambda s: abs(s - spot))
    cr = calls[calls.strike == atm].iloc[0]
    pr = puts[puts.strike == atm].iloc[0]
    cm, pm = _mid(cr), _mid(pr)
    if cm is None or pm is None:
        return ExpectedMove(False, f"El straddle {atm} del vencimiento {exp} no tiene precios usables.")

    straddle = cm + pm
    move_pct = straddle / spot * 100
    low, high = spot - straddle, spot + straddle

    hist_abs = [abs(m) for m in hist]
    hist_avg = sum(hist_abs) / len(hist_abs) if hist_abs else None
    inside_rate = (sum(1 for m in hist_abs if m <= move_pct) / len(hist_abs) * 100) if hist_abs else None

    # --- escalera de strikes alrededor del dinero -------------------------
    def hit_rate(pct: float, up: bool) -> Optional[float]:
        """% de earnings pasados cuyo movimiento alcanzó ese umbral en esa dirección."""
        if not hist:
            return None
        n = sum(1 for m in hist if (m >= pct if up else m <= -pct))
        return n / len(hist) * 100

    def hit_n(pct: float, up: bool) -> int:
        return sum(1 for m in hist if (m >= pct if up else m <= -pct))

    rows: list[StrikeRow] = []
    for kind, df, up in (("call", calls, True), ("put", puts, False)):
        cands = [s for s in common if (s >= atm if up else s <= atm)]
        cands = sorted(cands) if up else sorted(cands, reverse=True)
        cands = cands[:max_strikes]
        for s in cands:
            sub = df[df.strike == s]
            if sub.empty:
                continue
            r = sub.iloc[0]
            prem = _mid(r)
            be = (s + prem) if (up and prem is not None) else ((s - prem) if prem is not None else None)
            be_pct = ((be / spot - 1) * 100) if be else None
            dist = (s / spot - 1) * 100
            iv = _f(getattr(r, "impliedVolatility", None))
            rows.append(StrikeRow(
                kind=kind, strike=float(s), distance_pct=dist, premium=prem,
                breakeven=be, breakeven_pct=be_pct,
                hist_hit_strike=hit_rate(abs(dist), up) if dist else (100.0 if hist else None),
                hist_hit_breakeven=hit_rate(abs(be_pct), up) if be_pct is not None else None,
                hist_hit_n=hit_n(abs(be_pct), up) if be_pct is not None else 0,
                iv=iv if (iv and 0.01 < iv < 5) else None,
                open_interest=int(_f(getattr(r, "openInterest", None)) or 0),
                volume=int(_f(getattr(r, "volume", None)) or 0),
                inside_implied=low <= s <= high,
            ))

    atm_iv = None
    for v in (_f(cr.impliedVolatility), _f(pr.impliedVolatility)):
        if v and 0.01 < v < 5:
            atm_iv = v if atm_iv is None else (atm_iv + v) / 2

    return ExpectedMove(
        available=True, expiry=exp.isoformat(), days_to_expiry=(exp - today).days,
        covers_earnings=covers, spot=spot, atm_strike=float(atm),
        call_mid=cm, put_mid=pm, straddle=straddle,
        implied_move_pct=move_pct, implied_low=low, implied_high=high, atm_iv=atm_iv,
        hist_move_pct=hist_avg,
        premium_vs_hist=(move_pct - hist_avg) if hist_avg is not None else None,
        hist_inside_rate=inside_rate, n_hist=len(hist), strikes=rows,
    )
