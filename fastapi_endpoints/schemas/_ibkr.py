"""
schemas/ibkr.py — Pydantic models for IBKR order endpoints.
Matches exactly what ibkr_bridge.py sends and expects back.
"""
from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────

class OrderStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    FILLED    = "FILLED"
    CANCELLED = "CANCELLED"
    INACTIVE  = "INACTIVE"
    PENDING   = "PENDING"
    ERROR     = "ERROR"


class OrderAction(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LMT = "LMT"
    MKT = "MKT"
    MOC = "MOC"
    LOC = "LOC"


class TimeInForce(str, Enum):
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    GTD = "GTD"


# ─────────────────────────────────────────────────────────────────
# Leg schema — each option leg of the combo order
# ─────────────────────────────────────────────────────────────────

class OrderLeg(BaseModel):
    symbol:    str               = Field(..., description="Option root symbol")
    expiry:    str               = Field(..., description="YYYYMMDD or YYYY-MM-DD")
    strike:    float             = Field(..., gt=0)
    right:     str               = Field(..., pattern="^[CP]$", description="C or P")
    action:    OrderAction
    ratio:     int               = Field(1, ge=1, description="Number of contracts")
    exchange:  str               = "SMART"
    currency:  str               = "USD"
    sec_type:  str               = "OPT"


# ─────────────────────────────────────────────────────────────────
# Submit request — sent from ibkr_bridge.build_ibkr_payload()
# ─────────────────────────────────────────────────────────────────

class IBKRSubmitRequest(BaseModel):
    account:     str             = Field("", description="IB account number, e.g. U1234567")
    symbol:      str             = Field(..., description="Underlying ticker")
    sec_type:    str             = Field("BAG", description="Always BAG for combos")
    exchange:    str             = "SMART"
    currency:    str             = "USD"
    action:      OrderAction
    quantity:    int             = Field(..., ge=1, description="Number of combo contracts")
    order_type:  OrderType       = OrderType.LMT
    limit_price: float           = Field(..., ge=0)
    tif:         TimeInForce     = TimeInForce.DAY
    strategy:    str             = ""
    legs:        List[OrderLeg]  = Field(default_factory=list)
    client_tag:  str             = ""
    meta:        Dict[str, Any]  = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "account":     "U1234567",
                "symbol":      "SPY",
                "sec_type":    "BAG",
                "exchange":    "SMART",
                "currency":    "USD",
                "action":      "SELL",
                "quantity":    1,
                "order_type":  "LMT",
                "limit_price": 2.35,
                "tif":         "DAY",
                "strategy":    "Credit Spread",
                "legs": [
                    {"symbol":"SPY","expiry":"20260620","strike":540,"right":"P",
                     "action":"SELL","ratio":1,"exchange":"SMART","currency":"USD","sec_type":"OPT"},
                    {"symbol":"SPY","expiry":"20260620","strike":535,"right":"P",
                     "action":"BUY", "ratio":1,"exchange":"SMART","currency":"USD","sec_type":"OPT"},
                ],
                "client_tag":  "TI-abc123",
                "meta":        {"idea_id":"abc123","pop":72.5,"score":81.2,"max_loss":-265.0},
            }
        }


# ─────────────────────────────────────────────────────────────────
# Submit response
# ─────────────────────────────────────────────────────────────────

class IBKRSubmitResponse(BaseModel):
    order_id: int
    account:  str
    status:   OrderStatus = OrderStatus.SUBMITTED

    class Config:
        json_schema_extra = {
            "example": {"order_id": 10042, "account": "U1234567", "status": "SUBMITTED"}
        }


# ─────────────────────────────────────────────────────────────────
# Order status response
# ─────────────────────────────────────────────────────────────────

class IBKROrderStatusResponse(BaseModel):
    order_id:   int
    status:     OrderStatus
    filled_qty: int   = 0
    remaining:  int   = 0
    avg_fill:   float = 0.0
    message:    str   = ""

    class Config:
        json_schema_extra = {
            "example": {
                "order_id":   10042,
                "status":     "SUBMITTED",
                "filled_qty": 0,
                "remaining":  1,
                "avg_fill":   0.0,
                "message":    "",
            }
        }


# ─────────────────────────────────────────────────────────────────
# Cancel response
# ─────────────────────────────────────────────────────────────────

class IBKRCancelResponse(BaseModel):
    order_id: int
    status:   OrderStatus = OrderStatus.CANCELLED
    message:  str = ""

    class Config:
        json_schema_extra = {
            "example": {"order_id": 10042, "status": "CANCELLED", "message": ""}
        }
