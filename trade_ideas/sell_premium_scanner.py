"""
sell_premium_scanner.py — 0 DTE and 7 DTE Credit Spread Scanner

Specialized scanner for short-dated premium selling.
Handles the unique risk profiles of 0-day and 7-day expirations:
  - 0 DTE: same-day expiry, extreme gamma, intraday pricing, tight windows
  - 7 DTE: weekly theta acceleration sweet spot, standard credit spread logic

Scanner pipeline:
  1. fetch_chain()     — get strike/bid/ask/greeks for the target expiry
  2. filter_spreads()  — apply quality filters (delta, credit, width, B/A)
  3. score_spreads()   — rank by composite score (POP, credit-to-width, gamma risk)
  4. build_ideas()     — convert top candidates into TradeIdea objects
"""
from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Tuple

from .models import Greeks, IdeaScore, IdeaStatus, OptionLeg, StrategyType, TradeIdea, Trend

log = logging.getLogger("trade_ideas.sell_premium")


# ──────────────────────────────────────────────────────────────────
# DTE mode enum
# ──────────────────────────────────────────────────────────────────

class DTEMode(str, Enum):
    DTE_0  = "0 DTE"
    DTE_7  = "7 DTE"
    BOTH   = "Both"


# ──────────────────────────────────────────────────────────────────
# Filter parameters — tune per DTE mode
# ──────────────────────────────────────────────────────────────────

@dataclass
class ScanFilters:
    # Delta range for the short strike (absolute value)
    min_short_delta:   float = 0.10
    max_short_delta:   float = 0.30

    # Minimum net credit per spread (in dollars, per 1 contract = 100 shares)
    min_credit_dollars: float = 25.0

    # Maximum spread width in points
    max_width_points:  float = 10.0

    # Maximum bid-ask spread as % of mid price (liquidity filter)
    max_ba_pct:        float = 0.20   # 20% of mid

    # Minimum open interest on either leg
    min_oi:            int   = 50

    # Minimum POP threshold to include in results
    min_pop:           float = 65.0

    # Maximum gamma exposure per spread (absolute)
    max_gamma:         float = 0.08

    # Credit-to-width ratio floor (e.g. 0.20 = collect >= 20% of max loss)
    min_credit_width_ratio: float = 0.20


# Default filter sets per DTE mode
_FILTERS_0DTE = ScanFilters(
    min_short_delta=0.08,    # tighter delta — 0 DTE moves fast
    max_short_delta=0.25,
    min_credit_dollars=20.0, # lower threshold — premium crushed intraday
    max_width_points=5.0,    # narrower spreads — limit gamma exposure
    max_ba_pct=0.25,         # slightly wider B/A acceptable intraday
    min_oi=25,               # liquidity thinner on 0 DTE
    min_pop=60.0,            # slightly more aggressive
    max_gamma=0.12,          # higher gamma tolerance (we know it)
    min_credit_width_ratio=0.18,
)

_FILTERS_7DTE = ScanFilters(
    min_short_delta=0.12,
    max_short_delta=0.30,
    min_credit_dollars=35.0,
    max_width_points=10.0,
    max_ba_pct=0.18,
    min_oi=75,
    min_pop=65.0,
    max_gamma=0.06,
    min_credit_width_ratio=0.22,
)


# ──────────────────────────────────────────────────────────────────
# Strike data container (from option chain)
# ──────────────────────────────────────────────────────────────────

@dataclass
class StrikeData:
    strike:       float
    right:        str          # "C" or "P"
    bid:          float
    ask:          float
    delta:        float        # signed (calls +, puts -)
    gamma:        float
    theta:        float
    vega:         float
    iv:           float
    open_interest: int = 0
    volume:       int = 0
    expiry:       str = ""     # YYYYMMDD

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0 if self.bid > 0 else self.ask

    @property
    def ba_pct(self) -> float:
        """Bid-ask as fraction of mid."""
        if self.mid <= 0:
            return 1.0
        return (self.ask - self.bid) / self.mid

    @property
    def abs_delta(self) -> float:
        return abs(self.delta)


# ──────────────────────────────────────────────────────────────────
# Candidate spread
# ──────────────────────────────────────────────────────────────────

@dataclass
class SpreadCandidate:
    short_leg:  StrikeData
    long_leg:   StrikeData
    right:      str            # "C" or "P"
    dte:        int
    symbol:     str
    net_credit: float = 0.0    # dollars per spread (× 100 = per contract)
    width:      float = 0.0    # strike distance
    max_loss:   float = 0.0    # width - credit
    pop:        float = 0.0
    score:      float = 0.0
    grade:      str   = "F"
    cw_ratio:   float = 0.0    # credit / width ratio

    @property
    def net_delta(self) -> float:
        # Short delta dominates, partially offset by long
        return self.short_leg.delta + self.long_leg.delta

    @property
    def net_gamma(self) -> float:
        return self.short_leg.gamma + self.long_leg.gamma   # both same sign

    @property
    def net_theta(self) -> float:
        return self.short_leg.theta + self.long_leg.theta   # both negative; short wins

    @property
    def net_vega(self) -> float:
        return self.short_leg.vega + self.long_leg.vega


# ──────────────────────────────────────────────────────────────────
# POP calculation — DTE-aware
# ──────────────────────────────────────────────────────────────────

def pop_0dte(short_strike: float, underlying: float, iv: float,
             minutes_remaining: int = 180) -> float:
    """
    0 DTE POP using intraday time fraction.
    minutes_remaining: time left in trading session (default 3 hours).
    """
    if minutes_remaining <= 0 or iv <= 0 or underlying <= 0:
        return 50.0
    T = minutes_remaining / (252 * 390)   # fraction of a trading year (390 min/day)
    sig_sqT = iv * math.sqrt(T)
    if sig_sqT == 0:
        return 50.0
    d2 = math.log(short_strike / underlying) / sig_sqT - 0.5 * sig_sqT
    cdf = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2)))
    return round(cdf * 100.0, 1)


def pop_dte(short_strike: float, underlying: float, iv: float, dte: int) -> float:
    """Standard DTE-based POP (works for 1+ days)."""
    if dte <= 0:
        return pop_0dte(short_strike, underlying, iv, minutes_remaining=180)
    T = dte / 365.0
    sig_sqT = iv * math.sqrt(T)
    if sig_sqT == 0:
        return 50.0
    d2 = math.log(short_strike / underlying) / sig_sqT - 0.5 * sig_sqT
    cdf = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2)))
    return round(cdf * 100.0, 1)


# ──────────────────────────────────────────────────────────────────
# Composite scoring for credit spreads
# ──────────────────────────────────────────────────────────────────

def _score_spread(cand: SpreadCandidate, iv_rank: float, dte_mode: str) -> Tuple[float, str]:
    """
    Composite score (0-100) = weighted sum:
      POP score           35%  (primary driver)
      Credit/width ratio  25%  (premium quality)
      IV Rank score       20%  (environment fit)
      Liquidity score     12%  (B/A quality + OI)
      Gamma risk penalty   8%  (lower = better for 0 DTE)
    """
    # POP score
    pop_s = min(cand.pop, 95.0)   # cap at 95; > 95 is usually too close to ATM or bad data
    pop_score = _norm_range(pop_s, 55.0, 90.0)  # 55% POP → 0, 90% POP → 100

    # Credit-to-width ratio (0.15 → 0, 0.40 → 100)
    cw_score = _norm_range(cand.cw_ratio, 0.15, 0.45)

    # IV Rank — sellers want high IV (50–80 is sweet spot)
    if iv_rank <= 30:
        iv_s = iv_rank / 30.0 * 40.0
    elif iv_rank <= 70:
        iv_s = 40.0 + (iv_rank - 30.0) / 40.0 * 60.0
    else:
        iv_s = 100.0 - (iv_rank - 70.0) / 30.0 * 20.0
    iv_score = round(iv_s, 1)

    # Liquidity: tighter B/A and higher OI
    ba_pct = (cand.short_leg.ba_pct + cand.long_leg.ba_pct) / 2.0
    ba_score = max(0.0, 100.0 - ba_pct * 400.0)
    oi = min(cand.short_leg.open_interest, cand.long_leg.open_interest)
    oi_score = min(100.0, math.log1p(oi) / math.log1p(5000) * 100.0)
    liq_score = 0.5 * ba_score + 0.5 * oi_score

    # Gamma risk penalty — more gamma = more dangerous for 0 DTE
    # net_gamma for a short spread is negative (short > long, same sign)
    abs_gamma = abs(cand.net_gamma)
    gamma_penalty = min(100.0, abs_gamma / 0.15 * 100.0)  # 0.15 gamma = full penalty
    gamma_score = 100.0 - gamma_penalty

    # Extra gamma weight for 0 DTE
    if dte_mode == DTEMode.DTE_0:
        w = {"pop": 0.35, "cw": 0.22, "iv": 0.18, "liq": 0.10, "gamma": 0.15}
    else:
        w = {"pop": 0.35, "cw": 0.25, "iv": 0.20, "liq": 0.12, "gamma": 0.08}

    composite = (
        pop_score   * w["pop"]   +
        cw_score    * w["cw"]    +
        iv_score    * w["iv"]    +
        liq_score   * w["liq"]  +
        gamma_score * w["gamma"]
    )
    composite = round(min(max(composite, 0.0), 100.0), 1)

    if composite >= 80: grade = "A"
    elif composite >= 65: grade = "B"
    elif composite >= 50: grade = "C"
    elif composite >= 35: grade = "D"
    else: grade = "F"

    return composite, grade


def _norm_range(val: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 50.0
    return round(min(max((val - lo) / (hi - lo) * 100.0, 0.0), 100.0), 1)


# ──────────────────────────────────────────────────────────────────
# Mock chain generator — used when no live API is available
# ──────────────────────────────────────────────────────────────────

def generate_mock_chain(symbol: str, underlying: float, iv30: float,
                        dte: int) -> List[StrikeData]:
    """
    Generates a realistic mock option chain for dev/testing.
    Produces puts and calls across ±15% of underlying price.
    Uses simplified Black-Scholes approximation for greeks.
    """
    import random
    rng = random.Random(hash(symbol) ^ dte ^ int(underlying))

    T = max(dte, 0.01) / 365.0
    strikes = []
    step = max(1.0, round(underlying * 0.005))  # ~0.5% steps
    for i in range(-15, 16):
        strikes.append(round(underlying + i * step, 1))

    chain: List[StrikeData] = []
    for K in strikes:
        for right in ("C", "P"):
            # Approximate BS delta
            if T > 0 and iv30 > 0:
                sig_sqT = iv30 * math.sqrt(T)
                d1 = (math.log(underlying / K) + (0.5 * iv30**2) * T) / sig_sqT
                cdf_d1 = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2)))
                delta_c = cdf_d1
                delta_p = delta_c - 1.0
                gamma   = math.exp(-0.5 * d1**2) / (math.sqrt(2 * math.pi) *
                          underlying * sig_sqT) if sig_sqT > 0 else 0.0
                theta_c = -(underlying * iv30 * math.exp(-0.5 * d1**2)) / (
                          2 * math.sqrt(2 * math.pi * T)) / 365.0 if T > 0 else 0.0
                vega    = underlying * math.sqrt(T) * math.exp(-0.5 * d1**2) / math.sqrt(2 * math.pi) * 0.01
                # Intrinsic + time value approximation
                intrinsic_c = max(underlying - K, 0.0)
                intrinsic_p = max(K - underlying, 0.0)
                tv = underlying * iv30 * math.sqrt(T / (2 * math.pi))
                mid_c = intrinsic_c + tv
                mid_p = intrinsic_p + tv
            else:
                delta_c = 0.5; delta_p = -0.5; gamma = 0.02
                theta_c = -0.05; vega = 0.10
                mid_c = max(underlying - K, 0) + 0.50
                mid_p = max(K - underlying, 0) + 0.50

            spread_noise = rng.uniform(0.01, 0.08) * (mid_c if right == "C" else mid_p)
            mid = mid_c if right == "C" else mid_p
            mid = max(mid, 0.05)
            bid = round(max(mid - spread_noise / 2, 0.01), 2)
            ask = round(mid + spread_noise / 2, 2)
            oi  = rng.randint(0, 8000)
            vol = rng.randint(0, 2000)
            expiry = (date.today().strftime("%Y%m%d") if dte == 0
                      else (date.today().replace(
                          day=date.today().day + dte)).strftime("%Y%m%d"))

            chain.append(StrikeData(
                strike=K,
                right=right,
                bid=bid,
                ask=ask,
                delta=round(delta_c if right == "C" else delta_p, 4),
                gamma=round(gamma, 4),
                theta=round(theta_c, 4),
                vega=round(vega, 4),
                iv=round(iv30 * rng.uniform(0.85, 1.20), 4),
                open_interest=oi,
                volume=vol,
                expiry=expiry,
            ))
    return chain


# ──────────────────────────────────────────────────────────────────
# Main Scanner
# ──────────────────────────────────────────────────────────────────

class SellPremiumScanner:
    """
    Scans for the best credit spreads in 0 DTE and 7 DTE expirations.

    Usage:
        scanner = SellPremiumScanner(api_client=your_client)
        ideas   = scanner.scan("SPY", dte_mode=DTEMode.BOTH, market_data={...})
    """

    def __init__(self, api_client=None, dry_run: bool = True):
        self._api      = api_client
        self._dry_run  = dry_run

    # ── public entry point ──────────────────────────────────────────

    def scan(
        self,
        symbol:      str,
        dte_mode:    DTEMode,
        market_data: dict,
        contracts:   int = 1,
        max_ideas:   int = 10,
        minutes_remaining: int = 180,     # for 0 DTE POP calc
    ) -> List[TradeIdea]:
        """
        Run the sell premium scan.

        market_data keys expected:
            price, iv30, hv20, iv_rank, iv_pct, price_history
        """
        underlying = float(market_data.get("price", 0) or 0)
        iv30       = float(market_data.get("iv30", 0.25) or 0.25)
        iv_rank    = float(market_data.get("iv_rank", 50) or 50)

        if underlying <= 0:
            log.warning("scan: invalid underlying price for %s", symbol)
            return []

        target_dtes: List[int] = []
        if dte_mode in (DTEMode.DTE_0, DTEMode.BOTH):
            target_dtes.append(0)
        if dte_mode in (DTEMode.DTE_7, DTEMode.BOTH):
            target_dtes.append(7)

        all_ideas: List[TradeIdea] = []
        for dte in target_dtes:
            filters  = _FILTERS_0DTE if dte == 0 else _FILTERS_7DTE
            dm       = DTEMode.DTE_0 if dte == 0 else DTEMode.DTE_7
            chain    = self._fetch_chain(symbol, dte, underlying, iv30)
            if not chain:
                log.warning("No chain data for %s DTE=%d", symbol, dte)
                continue
            candidates = self._find_candidates(
                chain, underlying, iv30, iv_rank, dte, filters,
                minutes_remaining, dm,
            )
            candidates.sort(key=lambda c: c.score, reverse=True)
            top = candidates[:max_ideas]
            for cand in top:
                idea = self._to_trade_idea(cand, symbol, contracts, market_data)
                all_ideas.append(idea)

        # Sort combined list by score
        all_ideas.sort(key=lambda i: i.score.composite, reverse=True)
        return all_ideas[:max_ideas]

    # ── chain fetching ──────────────────────────────────────────────

    def _fetch_chain(self, symbol: str, dte: int,
                     underlying: float, iv30: float) -> List[StrikeData]:
        """Fetch chain from API or fall back to mock."""
        if self._api is not None:
            try:
                data = self._api.get(
                    f"/sell-premium/chain/{symbol}",
                    params={"dte": dte},
                    timeout=8,
                )
                if data and "chain" in data:
                    return [StrikeData(**s) for s in data["chain"]]
            except Exception as e:
                log.warning("chain fetch failed (%s DTE=%d): %s — using mock", symbol, dte, e)
        return generate_mock_chain(symbol, underlying, iv30, dte)

    # ── spread discovery ────────────────────────────────────────────

    def _find_candidates(
        self,
        chain:    List[StrikeData],
        underlying: float,
        iv30:     float,
        iv_rank:  float,
        dte:      int,
        filters:  ScanFilters,
        minutes_remaining: int,
        dte_mode: DTEMode,
    ) -> List[SpreadCandidate]:
        """Find all qualifying put spreads and call spreads."""
        candidates: List[SpreadCandidate] = []

        puts  = sorted([s for s in chain if s.right == "P"], key=lambda s: s.strike)
        calls = sorted([s for s in chain if s.right == "C"], key=lambda s: s.strike)

        # Put credit spreads (bull put spreads) — short OTM put, long further OTM put
        candidates += self._scan_spreads(
            strikes=puts,
            underlying=underlying,
            iv30=iv30,
            iv_rank=iv_rank,
            dte=dte,
            filters=filters,
            minutes_remaining=minutes_remaining,
            dte_mode=dte_mode,
            right="P",
            short_above_long=True,   # short higher strike put, long lower
        )
        # Call credit spreads (bear call spreads) — short OTM call, long further OTM call
        candidates += self._scan_spreads(
            strikes=calls,
            underlying=underlying,
            iv30=iv30,
            iv_rank=iv_rank,
            dte=dte,
            filters=filters,
            minutes_remaining=minutes_remaining,
            dte_mode=dte_mode,
            right="C",
            short_above_long=False,  # short lower strike call, long higher
        )
        return candidates

    def _scan_spreads(
        self,
        strikes:     List[StrikeData],
        underlying:  float,
        iv30:        float,
        iv_rank:     float,
        dte:         int,
        filters:     ScanFilters,
        minutes_remaining: int,
        dte_mode:    DTEMode,
        right:       str,
        short_above_long: bool,
    ) -> List[SpreadCandidate]:
        candidates = []
        for i, short in enumerate(strikes):
            if not (filters.min_short_delta <= short.abs_delta <= filters.max_short_delta):
                continue
            if short.ba_pct > filters.max_ba_pct:
                continue
            if short.open_interest < filters.min_oi:
                continue

            # Find valid long legs (further OTM)
            if short_above_long:
                long_candidates = [s for s in strikes if s.strike < short.strike]
            else:
                long_candidates = [s for s in strikes if s.strike > short.strike]

            for long in long_candidates:
                width = abs(short.strike - long.strike)
                if width > filters.max_width_points:
                    continue
                if long.ba_pct > filters.max_ba_pct:
                    continue
                if long.open_interest < filters.min_oi:
                    continue

                net_credit_pts = short.mid - long.mid
                if net_credit_pts <= 0:
                    continue
                net_credit_dlr = round(net_credit_pts * 100.0, 2)
                if net_credit_dlr < filters.min_credit_dollars:
                    continue

                cw_ratio = net_credit_pts / width if width > 0 else 0.0
                if cw_ratio < filters.min_credit_width_ratio:
                    continue

                # POP calculation
                if dte == 0:
                    pop = pop_0dte(short.strike, underlying, short.iv or iv30,
                                   minutes_remaining)
                else:
                    pop = pop_dte(short.strike, underlying, short.iv or iv30, dte)
                if pop < filters.min_pop:
                    continue

                # Build candidate
                cand = SpreadCandidate(
                    short_leg  = short,
                    long_leg   = long,
                    right      = right,
                    dte        = dte,
                    symbol     = "",
                    net_credit = net_credit_dlr,
                    width      = width,
                    max_loss   = round((width - net_credit_pts) * 100.0, 2),
                    pop        = pop,
                    cw_ratio   = cw_ratio,
                )

                # Gamma filter
                if abs(cand.net_gamma) > filters.max_gamma:
                    continue

                cand.score, cand.grade = _score_spread(cand, iv_rank, dte_mode)
                candidates.append(cand)

        return candidates

    # ── convert to TradeIdea ─────────────────────────────────────────

    def _to_trade_idea(
        self,
        cand:        SpreadCandidate,
        symbol:      str,
        contracts:   int,
        market_data: dict,
    ) -> TradeIdea:
        right_label = "Put CS" if cand.right == "P" else "Call CS"
        dte_label   = "0DTE" if cand.dte == 0 else "7DTE"
        strategy_lbl = f"{dte_label} {right_label}"

        expiry = cand.short_leg.expiry or ""

        short_leg = OptionLeg(
            symbol    = symbol,
            expiry    = expiry,
            strike    = cand.short_leg.strike,
            right     = cand.right,
            action    = "SELL",
            qty       = contracts,
            mid_price = cand.short_leg.mid,
            greeks    = Greeks(
                delta = cand.short_leg.delta,
                gamma = cand.short_leg.gamma,
                theta = cand.short_leg.theta,
                vega  = cand.short_leg.vega,
                iv    = cand.short_leg.iv,
            ),
        )
        long_leg = OptionLeg(
            symbol    = symbol,
            expiry    = expiry,
            strike    = cand.long_leg.strike,
            right     = cand.right,
            action    = "BUY",
            qty       = contracts,
            mid_price = cand.long_leg.mid,
            greeks    = Greeks(
                delta = cand.long_leg.delta,
                gamma = cand.long_leg.gamma,
                theta = cand.long_leg.theta,
                vega  = cand.long_leg.vega,
                iv    = cand.long_leg.iv,
            ),
        )

        net_g = Greeks(
            delta = round(cand.net_delta * contracts, 4),
            gamma = round(cand.net_gamma * contracts, 4),
            theta = round(cand.net_theta * contracts, 4),
            vega  = round(cand.net_vega  * contracts, 4),
        )

        # IdeaScore components
        iv_rank  = float(market_data.get("iv_rank", 50) or 50)
        iv30     = float(market_data.get("iv30", 0.25) or 0.25)
        hv20     = float(market_data.get("hv20", 0.20) or 0.20)
        price_h  = market_data.get("price_history", [])

        from .strategy_engine import _compute_iv_rank_score, detect_trend, _liquidity_score
        pop_sc  = _norm_range(cand.pop, 55.0, 90.0)
        iv_sc   = _compute_iv_rank_score(iv_rank)
        liq_sc  = _liquidity_score(cand.short_leg.bid, cand.short_leg.ask,
                              cand.short_leg.open_interest)
        cw_sc   = _norm_range(cand.cw_ratio, 0.15, 0.45)
        trend   = detect_trend(price_h, iv_rank, hv20, iv30)

        idea_score = IdeaScore(
            pop_score       = pop_sc,
            iv_rank_score   = iv_sc,
            trend_score     = cw_sc,        # re-use trend slot for C/W quality
            reward_risk     = cw_sc,
            liquidity_score = liq_sc,
        )
        # Override composite with our DTE-aware score
        idea_score._dte_composite = cand.score   # stored for display

        idea = TradeIdea(
            id            = str(uuid.uuid4())[:8].upper(),
            symbol        = symbol,
            strategy      = StrategyType.CREDIT_SPREAD,
            dte           = cand.dte,
            contracts     = contracts,
            legs          = [short_leg, long_leg],
            score         = idea_score,
            net_credit    = cand.net_credit * contracts,
            max_profit    = cand.net_credit * contracts,
            max_loss      = cand.max_loss   * contracts,
            breakevens    = [round(cand.short_leg.strike -
                            (cand.net_credit / 100.0), 2)],
            pop           = cand.pop,
            iv_rank       = iv_rank,
            iv_pct        = float(market_data.get("iv_pct", 50) or 50),
            trend         = trend,
            underlying_px = float(market_data.get("price", 0) or 0),
            net_greeks    = net_g,
            status        = IdeaStatus.PENDING,
            notes         = (
                f"{strategy_lbl} | Short {cand.right}{cand.short_leg.strike:.1f} / "
                f"Long {cand.right}{cand.long_leg.strike:.1f} | "
                f"Width ${cand.width:.0f} | C/W {cand.cw_ratio:.0%} | "
                f"γ {cand.net_gamma:+.4f}"
            ),
        )
        return idea
