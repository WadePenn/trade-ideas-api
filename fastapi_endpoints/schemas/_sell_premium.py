"""
schemas/sell_premium.py — Pydantic models for the Sell Premium scan endpoint.
Matches exactly what SellPremiumScanner expects and returns.
"""
from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class DTEMode(str, Enum):
    DTE_0 = "0 DTE"
    DTE_7 = "7 DTE"
    BOTH  = "Both"


# ── Option chain strike (inbound from data provider, outbound to scanner) ──────

class StrikeSchema(BaseModel):
    strike:        float
    right:         str   = Field(..., pattern="^[CP]$")
    bid:           float
    ask:           float
    delta:         float
    gamma:         float
    theta:         float
    vega:          float
    iv:            float
    open_interest: int   = 0
    volume:        int   = 0
    expiry:        str   = ""   # YYYYMMDD


# ── Scan request ───────────────────────────────────────────────────────────────

class SellPremiumScanRequest(BaseModel):
    symbol:            str       = Field(..., min_length=1, max_length=10)
    dte_mode:          DTEMode   = DTEMode.DTE_7
    contracts:         int       = Field(1, ge=1, le=100)
    max_results:       int       = Field(10, ge=1, le=50)
    minutes_remaining: int       = Field(180, ge=1, le=390,
                                        description="Minutes left in session (0 DTE only)")

    # Optional filter overrides (server uses sensible defaults per DTE mode)
    min_short_delta:        Optional[float] = None
    max_short_delta:        Optional[float] = None
    min_credit_dollars:     Optional[float] = None
    max_width_points:       Optional[float] = None
    max_ba_pct:             Optional[float] = None
    min_pop:                Optional[float] = None
    min_credit_width_ratio: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "symbol":    "SPY",
                "dte_mode":  "7 DTE",
                "contracts": 1,
                "max_results": 10,
                "minutes_remaining": 180,
            }
        }


# ── Individual spread result ───────────────────────────────────────────────────

class SpreadResult(BaseModel):
    id:              str
    symbol:          str
    dte:             int
    right:           str        # "P" or "C"
    short_strike:    float
    long_strike:     float
    expiry:          str        # YYYYMMDD
    net_credit_dlr:  float      # per contract (× qty for total)
    max_loss_dlr:    float
    width_pts:       float
    credit_width_ratio: float
    pop:             float      # probability of profit 0-100
    score:           float      # composite 0-100
    grade:           str        # A/B/C/D/F
    short_delta:     float
    net_gamma:       float
    net_theta:       float
    net_vega:        float
    short_iv:        float
    short_oi:        int
    long_oi:         int
    notes:           str = ""


# ── Scan response ──────────────────────────────────────────────────────────────

class SellPremiumScanResponse(BaseModel):
    symbol:      str
    dte_mode:    DTEMode
    scan_time:   str            # ISO datetime
    iv_rank:     float
    iv30:        float
    underlying:  float
    total_found: int
    spreads:     List[SpreadResult]


# ── Chain request/response (for the panel's chain fetch) ─────────────────────

class ChainRequest(BaseModel):
    symbol: str
    dte:    int = Field(..., ge=0, le=45)


class ChainResponse(BaseModel):
    symbol:  str
    dte:     int
    expiry:  str
    chain:   List[StrikeSchema]
