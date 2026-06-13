"""
schemas/market.py — Pydantic models for market data endpoints.
Matches exactly what TradeIdeasPanel expects from api_client.get().
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class MarketSnapshotResponse(BaseModel):
    """
    Response for GET /market/snapshot/{symbol}.
    Field names must match exactly — the Trade Ideas panel reads them by key.
    """
    symbol:        str
    price:         float = Field(..., description="Last trade price")
    iv30:          float = Field(..., description="30-day implied vol (decimal, e.g. 0.28)")
    hv20:          float = Field(..., description="20-day historical vol (decimal, e.g. 0.20)")
    iv_rank:       float = Field(..., ge=0, le=100, description="IV Rank 0-100")
    iv_pct:        float = Field(..., ge=0, le=100, description="IV Percentile 0-100")
    price_history: List[float] = Field(
        default_factory=list,
        description="Recent daily closes, oldest first, at least 20 bars"
    )

    # Optional extras — panel ignores unknown fields
    bid:           Optional[float] = None
    ask:           Optional[float] = None
    volume:        Optional[int]   = None
    open_interest: Optional[int]   = None
    market_cap:    Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "symbol":        "SPY",
                "price":         545.23,
                "iv30":          0.28,
                "hv20":          0.20,
                "iv_rank":       62.0,
                "iv_pct":        58.0,
                "price_history": [538.1, 540.2, 541.5, 543.0, 542.8,
                                   544.1, 545.0, 543.5, 544.9, 545.2,
                                   546.0, 544.5, 543.8, 544.2, 545.0,
                                   545.5, 544.8, 545.1, 545.5, 545.2],
                "bid":           545.20,
                "ask":           545.25,
            }
        }


class MarketSnapshotError(BaseModel):
    symbol:  str
    error:   str
    detail:  Optional[str] = None
