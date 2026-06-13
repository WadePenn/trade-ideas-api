"""
services/sell_premium_service.py — Server-side sell premium scan service.

Called by routers/sell_premium.py.
Uses yfinance for price data and generates a mock chain by default.
Wire in IBKRProvider for real option chain data from TWS/Gateway.
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

from ..schemas.sell_premium import (
    ChainResponse,
    DTEMode,
    SellPremiumScanRequest,
    SellPremiumScanResponse,
    SpreadResult,
    StrikeSchema,
)

log = logging.getLogger("fastapi_api.sell_premium")


# ─────────────────────────────────────────────────────────────────
# Singleton service instance (injected via FastAPI Depends)
# ─────────────────────────────────────────────────────────────────

_service: Optional["SellPremiumService"] = None


def get_sell_premium_service() -> "SellPremiumService":
    global _service
    if _service is None:
        _service = SellPremiumService()
    return _service


def init_sell_premium_service(service: "SellPremiumService") -> None:
    global _service
    _service = service


# ─────────────────────────────────────────────────────────────────
# IV + market helpers
# ─────────────────────────────────────────────────────────────────

def _compute_hv(closes: list, window: int = 20) -> float:
    if len(closes) < window + 1:
        window = len(closes) - 1
    if window < 2:
        return 0.20
    import statistics
    recent = closes[-(window + 1):]
    logs = [math.log(recent[i] / recent[i - 1])
            for i in range(1, len(recent))
            if recent[i - 1] > 0 and recent[i] > 0]
    return round(statistics.stdev(logs) * math.sqrt(252), 4) if len(logs) >= 2 else 0.20


def _compute_iv_rank(current_iv: float, iv_history: list, lookback: int = 252) -> float:
    hist = iv_history[-lookback:] if len(iv_history) >= lookback else iv_history
    if not hist:
        return 50.0
    lo, hi = min(hist), max(hist)
    if hi == lo:
        return 50.0
    return round(min(max((current_iv - lo) / (hi - lo) * 100, 0), 100), 1)


def _dte_expiry(dte: int) -> str:
    target = date.today() + timedelta(days=dte)
    # Snap 0 DTE to today
    return target.strftime("%Y%m%d")


# ─────────────────────────────────────────────────────────────────
# Black-Scholes helpers for mock chain generation
# ─────────────────────────────────────────────────────────────────

def _bs_greeks(S: float, K: float, T: float, sigma: float):
    """Returns (delta_c, delta_p, gamma, theta_c, vega) using simplified BS."""
    if T <= 0 or sigma <= 0:
        return 0.5, -0.5, 0.02, -0.05, 0.10
    sig_sqT = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * sigma ** 2 * T) / sig_sqT
    d2 = d1 - sig_sqT
    phi_d1 = math.exp(-0.5 * d1 ** 2) / math.sqrt(2 * math.pi)
    cdf_d1 = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2)))
    cdf_d2 = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2)))
    delta_c = cdf_d1
    delta_p = delta_c - 1.0
    gamma   = phi_d1 / (S * sig_sqT)
    theta_c = -(S * sigma * phi_d1) / (2 * math.sqrt(T)) / 365.0
    vega    = S * math.sqrt(T) * phi_d1 * 0.01
    return delta_c, delta_p, gamma, theta_c, vega


def _mid_price(S: float, K: float, T: float, sigma: float, right: str) -> float:
    """Intrinsic + time value approximation."""
    tv = S * sigma * math.sqrt(max(T, 1 / (252 * 390))) / math.sqrt(2 * math.pi)
    intrinsic = max(S - K, 0) if right == "C" else max(K - S, 0)
    return max(round(intrinsic + tv, 2), 0.05)


# ─────────────────────────────────────────────────────────────────
# Main service
# ─────────────────────────────────────────────────────────────────

class SellPremiumService:
    """
    Server-side implementation of the sell premium scanner.
    Generates a realistic option chain and filters/scores spreads.
    """

    def __init__(self):
        try:
            import yfinance as yf
            self._yf = yf
            log.info("SellPremiumService: yfinance provider ready")
        except ImportError:
            self._yf = None
            log.warning("SellPremiumService: yfinance not installed — using synthetic data")

    # ── public API ─────────────────────────────────────────────────

    def scan(self, req: SellPremiumScanRequest) -> SellPremiumScanResponse:
        sym = req.symbol.upper()
        market = self._get_market_data(sym)
        S        = market["price"]
        iv30     = market["iv30"]
        iv_rank  = market["iv_rank"]

        target_dtes: List[int] = []
        if req.dte_mode in (DTEMode.DTE_0, DTEMode.BOTH):
            target_dtes.append(0)
        if req.dte_mode in (DTEMode.DTE_7, DTEMode.BOTH):
            target_dtes.append(7)

        all_spreads: List[SpreadResult] = []
        for dte in target_dtes:
            chain   = self._build_chain(sym, S, iv30, dte)
            spreads = self._scan_chain(
                chain, S, iv30, iv_rank, dte, req,
            )
            all_spreads.extend(spreads)

        # Sort by score desc, limit results
        all_spreads.sort(key=lambda s: s.score, reverse=True)
        top = all_spreads[:req.max_results]

        return SellPremiumScanResponse(
            symbol      = sym,
            dte_mode    = req.dte_mode,
            scan_time   = datetime.utcnow().isoformat() + "Z",
            iv_rank     = iv_rank,
            iv30        = iv30,
            underlying  = S,
            total_found = len(top),
            spreads     = top,
        )

    def get_chain(self, symbol: str, dte: int) -> ChainResponse:
        sym    = symbol.upper()
        market = self._get_market_data(sym)
        chain  = self._build_chain(sym, market["price"], market["iv30"], dte)
        expiry = _dte_expiry(dte)
        return ChainResponse(
            symbol = sym,
            dte    = dte,
            expiry = expiry,
            chain  = chain,
        )

    # ── market data ────────────────────────────────────────────────

    def _get_market_data(self, sym: str) -> dict:
        if self._yf is not None:
            try:
                ticker = self._yf.Ticker(sym)
                hist   = ticker.history(period="1y")
                if not hist.empty:
                    closes  = list(hist["Close"].tolist())
                    price   = round(float(closes[-1]), 2)
                    hv20    = _compute_hv(closes, 20)
                    iv30    = round(hv20 * 1.15, 4)   # yfinance has no option IV30
                    iv_hist = [hv20 * (1 + i * 0.002) for i in range(len(closes))]
                    iv_rank = _compute_iv_rank(iv30, iv_hist)
                    return {
                        "price":    price,
                        "iv30":     iv30,
                        "hv20":     hv20,
                        "iv_rank":  iv_rank,
                        "iv_pct":   iv_rank * 0.9,
                        "price_history": closes[-25:],
                    }
            except Exception as exc:
                log.warning("yfinance fetch for %s failed: %s", sym, exc)

        # Synthetic fallback
        import random
        _BASE = {"SPY": 549.0, "QQQ": 482.0, "IWM": 217.0, "AAPL": 218.0,
                 "TSLA": 315.0, "NVDA": 875.0, "AMZN": 197.0, "MSFT": 438.0}
        px  = _BASE.get(sym, 150.0) + random.uniform(-5, 5)
        iv  = round(random.uniform(0.18, 0.42), 3)
        ivr = round(random.uniform(30, 75), 1)
        return {
            "price": round(px, 2), "iv30": iv,
            "hv20": round(iv * 0.85, 3), "iv_rank": ivr,
            "iv_pct": round(ivr * 0.90, 1),
            "price_history": [px * (1 + random.uniform(-0.006, 0.006)) for _ in range(25)],
        }

    # ── chain builder ──────────────────────────────────────────────

    def _build_chain(self, sym: str, S: float, iv30: float,
                     dte: int) -> List[StrikeSchema]:
        """Generate a realistic option chain."""
        import random
        rng = random.Random(hash(sym) ^ dte ^ int(S * 100))
        step = max(1.0, round(S * 0.005, 0))
        strikes = [round(S + i * step, 1) for i in range(-15, 16)]
        expiry  = _dte_expiry(dte)
        T       = max(dte, 0.02) / 365.0   # never exactly zero for math

        chain: List[StrikeSchema] = []
        for K in strikes:
            for right in ("C", "P"):
                dc, dp, gamma, theta, vega = _bs_greeks(S, K, T, iv30)
                mid  = _mid_price(S, K, T, iv30, right)
                noise= rng.uniform(0.01, 0.07) * mid
                bid  = round(max(mid - noise / 2, 0.01), 2)
                ask  = round(mid + noise / 2, 2)
                iv_s = round(iv30 * rng.uniform(0.88, 1.18), 4)
                oi   = rng.randint(0, 8000)
                vol  = rng.randint(0, 2000)
                chain.append(StrikeSchema(
                    strike=K, right=right,
                    bid=bid, ask=ask,
                    delta=round(dc if right == "C" else dp, 4),
                    gamma=round(gamma, 4),
                    theta=round(theta, 4),
                    vega=round(vega, 4),
                    iv=iv_s,
                    open_interest=oi,
                    volume=vol,
                    expiry=expiry,
                ))
        return chain

    # ── spread scanner ─────────────────────────────────────────────

    def _scan_chain(
        self,
        chain:    List[StrikeSchema],
        S:        float,
        iv30:     float,
        iv_rank:  float,
        dte:      int,
        req:      SellPremiumScanRequest,
    ) -> List[SpreadResult]:
        # Default filters per DTE
        if dte == 0:
            min_d = req.min_short_delta or 0.08
            max_d = req.max_short_delta or 0.25
            min_cr= req.min_credit_dollars or 20.0
            max_w = req.max_width_points or 5.0
            max_ba= req.max_ba_pct or 0.25
            min_p = req.min_pop or 60.0
            min_cw= req.min_credit_width_ratio or 0.18
        else:
            min_d = req.min_short_delta or 0.12
            max_d = req.max_short_delta or 0.30
            min_cr= req.min_credit_dollars or 35.0
            max_w = req.max_width_points or 10.0
            max_ba= req.max_ba_pct or 0.18
            min_p = req.min_pop or 65.0
            min_cw= req.min_credit_width_ratio or 0.22

        puts  = sorted([s for s in chain if s.right == "P"], key=lambda x: x.strike)
        calls = sorted([s for s in chain if s.right == "C"], key=lambda x: x.strike)
        results: List[SpreadResult] = []

        for legs in [(puts, "P", True), (calls, "C", False)]:
            strikes, right, short_above = legs
            for short in strikes:
                abs_d = abs(short.delta)
                if not (min_d <= abs_d <= max_d):
                    continue
                mid_s = (short.bid + short.ask) / 2.0
                ba_s  = (short.ask - short.bid) / mid_s if mid_s > 0 else 1.0
                if ba_s > max_ba or short.open_interest < 25:
                    continue

                longs = ([s for s in strikes if s.strike < short.strike]
                         if short_above else
                         [s for s in strikes if s.strike > short.strike])

                for long in longs:
                    width = abs(short.strike - long.strike)
                    if width > max_w:
                        continue
                    mid_l = (long.bid + long.ask) / 2.0
                    ba_l  = (long.ask - long.bid) / mid_l if mid_l > 0 else 1.0
                    if ba_l > max_ba or long.open_interest < 25:
                        continue

                    net_pts = mid_s - mid_l
                    if net_pts <= 0:
                        continue
                    net_dlr = round(net_pts * 100.0, 2)
                    if net_dlr < min_cr:
                        continue
                    cw_ratio = net_pts / width if width > 0 else 0.0
                    if cw_ratio < min_cw:
                        continue

                    # POP
                    iv_use = short.iv or iv30
                    if dte == 0:
                        T_min = req.minutes_remaining / (252 * 390)
                        sig_sqT = iv_use * math.sqrt(T_min) if T_min > 0 else 0
                    else:
                        sig_sqT = iv_use * math.sqrt(dte / 365.0)
                    if sig_sqT > 0:
                        d2  = math.log(short.strike / S) / sig_sqT - 0.5 * sig_sqT
                        pop = round(0.5 * (1 + math.erf(d2 / math.sqrt(2))) * 100, 1)
                    else:
                        pop = 50.0
                    if pop < min_p:
                        continue

                    # Net greeks
                    net_gamma = short.gamma + long.gamma  # both same sign
                    net_theta = short.theta + long.theta
                    net_vega  = short.vega  + long.vega

                    # Score
                    pop_s  = min(max((pop - 55) / 35 * 100, 0), 100)
                    cw_s   = min(max((cw_ratio - 0.15) / 0.30 * 100, 0), 100)
                    if iv_rank <= 30:  iv_s = iv_rank / 30 * 40
                    elif iv_rank <= 70: iv_s = 40 + (iv_rank - 30) / 40 * 60
                    else: iv_s = 100 - (iv_rank - 70) / 30 * 20
                    ba_avg = (ba_s + ba_l) / 2
                    liq_s  = max(0, 100 - ba_avg * 400)
                    cap    = 0.12 if dte == 0 else 0.07
                    gam_s  = 100 - min(abs(net_gamma) / cap * 100, 100)
                    if dte == 0:
                        score = (pop_s*0.35 + cw_s*0.22 + iv_s*0.18 + liq_s*0.10 + gam_s*0.15)
                    else:
                        score = (pop_s*0.35 + cw_s*0.25 + iv_s*0.20 + liq_s*0.12 + gam_s*0.08)
                    score = round(min(max(score, 0), 100), 1)
                    if score < 10:
                        continue
                    grade = ("A" if score >= 80 else "B" if score >= 65
                             else "C" if score >= 50 else "D" if score >= 35 else "F")

                    results.append(SpreadResult(
                        id             = str(uuid.uuid4())[:8].upper(),
                        symbol         = req.symbol.upper(),
                        dte            = dte,
                        right          = right,
                        short_strike   = short.strike,
                        long_strike    = long.strike,
                        expiry         = short.expiry,
                        net_credit_dlr = net_dlr,
                        max_loss_dlr   = round((width - net_pts) * 100, 2),
                        width_pts      = width,
                        credit_width_ratio = round(cw_ratio, 4),
                        pop            = pop,
                        score          = score,
                        grade          = grade,
                        short_delta    = short.delta,
                        net_gamma      = round(net_gamma, 4),
                        net_theta      = round(net_theta, 4),
                        net_vega       = round(net_vega, 4),
                        short_iv       = short.iv,
                        short_oi       = short.open_interest,
                        long_oi        = long.open_interest,
                        notes          = (
                            f"{'0DTE' if dte==0 else '7DTE'} "
                            f"{'Put CS' if right=='P' else 'Call CS'} | "
                            f"Short {right}{short.strike:.1f} / Long {right}{long.strike:.1f} | "
                            f"Width ${width:.0f} | C/W {cw_ratio:.0%} | "
                            f"gamma {net_gamma:+.4f}"
                        ),
                    ))
        return results
