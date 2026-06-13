from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from .enums import OptionSide, OrderSide, SpreadType, OrderIntent

class OptionLegSpec(BaseModel):
    symbol: str
    expiry: date
    strike: float
    side: OptionSide
    order_side: OrderSide
    quantity: int = Field(gt=0)

class VerticalRequest(BaseModel):
    symbol: str
    expiry: date
    short_strike: float
    long_strike: float
    side: OptionSide
    quantity: int = Field(gt=0)
    intent: OrderIntent = OrderIntent.OPEN

    @validator("long_strike")
    def validate_width(cls, v, values):
        if values.get("short_strike") == v:
            raise ValueError("long_strike must differ from short_strike")
        return v

class IronCondorRequest(BaseModel):
    symbol: str
    expiry: date
    short_call_strike: float
    long_call_strike: float
    short_put_strike: float
    long_put_strike: float
    quantity: int = Field(gt=0)
    intent: OrderIntent = OrderIntent.OPEN

class CalendarRequest(BaseModel):
    symbol: str
    near_expiry: date
    far_expiry: date
    strike: float
    side: OptionSide
    quantity: int = Field(gt=0)
    intent: OrderIntent = OrderIntent.OPEN

class RollRequest(BaseModel):
    symbol: str
    current_expiry: date
    current_strike: float
    current_side: OptionSide
    target_expiry: date
    target_strike: float
    quantity: int = Field(gt=0)

class RiskCheckResult(BaseModel):
    ok: bool
    reason: Optional[str] = None

class OrderResult(BaseModel):
    success: bool
    order_ids: List[int] = []
    message: Optional[str] = None
    risk: Optional[RiskCheckResult] = None
    spread_type: Optional[SpreadType] = None
