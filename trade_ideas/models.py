"""models.py — Pure dataclasses, no external deps."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class StrategyType(str, Enum):
    CREDIT_SPREAD  = "Credit Spread"
    DEBIT_SPREAD   = "Debit Spread"
    IRON_CONDOR    = "Iron Condor"
    CALENDAR       = "Calendar"
    AUTO           = "Auto (Best Fit)"


class Trend(str, Enum):
    BULLISH  = "Bullish"
    BEARISH  = "Bearish"
    NEUTRAL  = "Neutral"
    VOLATILE = "Volatile"


class IdeaStatus(str, Enum):
    PENDING   = "Pending"
    SENT      = "Sent to IBKR"
    REJECTED  = "Rejected"
    FILLED    = "Filled"
    CANCELLED = "Cancelled"


@dataclass
class IdeaScore:
    pop_score:       float = 0.0
    iv_rank_score:   float = 0.0
    trend_score:     float = 0.0
    reward_risk:     float = 0.0
    liquidity_score: float = 0.0

    @property
    def composite(self) -> float:
        raw = (self.pop_score * 0.30 + self.iv_rank_score * 0.25
               + self.trend_score * 0.20 + self.reward_risk * 0.15
               + self.liquidity_score * 0.10)
        return round(min(max(raw, 0.0), 100.0), 1)

    @property
    def grade(self) -> str:
        c = self.composite
        if c >= 80: return "A"
        if c >= 65: return "B"
        if c >= 50: return "C"
        if c >= 35: return "D"
        return "F"

    @property
    def color_tag(self) -> str:
        c = self.composite
        if c >= 80: return "score_excellent"
        if c >= 65: return "score_good"
        if c >= 50: return "score_fair"
        return "score_poor"


@dataclass
class Greeks:
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega:  float = 0.0
    rho:   float = 0.0
    iv:    float = 0.0


@dataclass
class OptionLeg:
    symbol:    str
    expiry:    str
    strike:    float
    right:     str
    action:    str
    qty:       int
    mid_price: float = 0.0
    greeks:    Greeks = field(default_factory=Greeks)


@dataclass
class TradeIdea:
    id:            str
    symbol:        str
    strategy:      StrategyType
    dte:           int
    contracts:     int
    legs:          list = field(default_factory=list)
    score:         IdeaScore = field(default_factory=IdeaScore)
    net_credit:    float = 0.0
    max_profit:    float = 0.0
    max_loss:      float = 0.0
    breakevens:    list = field(default_factory=list)
    pop:           float = 0.0
    iv_rank:       float = 0.0
    iv_pct:        float = 0.0
    trend:         Trend = Trend.NEUTRAL
    underlying_px: float = 0.0
    net_greeks:    Greeks = field(default_factory=Greeks)
    status:        IdeaStatus = IdeaStatus.PENDING
    generated_at:  datetime = field(default_factory=datetime.utcnow)
    notes:         str = ""
    ibkr_order_id: Optional[int] = None
    ibkr_account:  Optional[str] = None

    @property
    def reward_risk_ratio(self) -> float:
        if self.max_loss == 0:
            return 0.0
        return round(self.max_profit / abs(self.max_loss), 2)

    @property
    def display_net(self) -> str:
        sign = "CR" if self.net_credit >= 0 else "DB"
        return f"${abs(self.net_credit):.2f} {sign}"

    def to_order_dict(self) -> dict:
        return {
            "symbol":    self.symbol,
            "strategy":  self.strategy.value,
            "dte":       self.dte,
            "contracts": self.contracts,
            "legs": [{"symbol": l.symbol, "expiry": l.expiry, "strike": l.strike,
                       "right": l.right, "action": l.action, "qty": l.qty,
                       "mid_price": l.mid_price} for l in self.legs],
            "net_credit": self.net_credit,
            "max_loss":   self.max_loss,
            "pop":        self.pop,
            "score":      self.score.composite,
        }
class StrategyType(str, Enum):
    CREDIT_SPREAD     = "Credit Spread"
    DEBIT_SPREAD      = "Debit Spread"
    IRON_CONDOR       = "Iron Condor"
    CALENDAR          = "Calendar"
    AUTO              = "Auto (Best Fit)"
class StrategyType(str, Enum):
    CREDIT_SPREAD      = "Credit Spread"
    DEBIT_SPREAD       = "Debit Spread"
    IRON_CONDOR        = "Iron Condor"
    CALENDAR           = "Calendar"
    AUTO               = "Auto (Best Fit)"
     # ── NEW ──────────────────────────────
    SELL_PREMIUM_0DTE = "Sell Premium 0DTE"
    SELL_PREMIUM_7DTE = "Sell Premium 7DTE"
    SELL_PREMIUM_BOTH = "Sell Premium 0+7DTE"
