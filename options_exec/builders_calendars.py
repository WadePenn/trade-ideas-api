from typing import List, Tuple
from ib_insync import Contract, ComboLeg

from .contracts import make_option_contract, make_combo_leg
from .enums import OrderSide, SpreadType
from .ibkr_client import get_ibkr_client
from .models import CalendarRequest, OrderResult
from .risk import check_notional_risk


def compute_calendar_risk_per_contract() -> float:
    # Calendar spreads are time‑based; treat as 1x placeholder risk
    return 1.0


def build_calendar_contracts(req: CalendarRequest) -> Tuple[List[Contract], List[OrderSide]]:
    near = make_option_contract(
        symbol=req.symbol,
        expiry=req.near_expiry,
        strike=req.strike,
        side=req.side,
    )
    far = make_option_contract(
        symbol=req.symbol,
        expiry=req.far_expiry,
        strike=req.strike,
        side=req.side,
    )

    if req.intent == "OPEN":
        # Classic calendar: short near, long far
        sides = [OrderSide.SELL, OrderSide.BUY]
    else:
        sides = [OrderSide.BUY, OrderSide.SELL]

    return [near, far], sides


def execute_calendar(req: CalendarRequest) -> OrderResult:
    per_contract_risk = compute_calendar_risk_per_contract()
    risk = check_notional_risk(per_contract_risk, req.quantity, SpreadType.CALENDAR)

    if not risk.ok:
        return OrderResult(
            success=False,
            order_ids=[],
            message=risk.reason,
            risk=risk,
            spread_type=SpreadType.CALENDAR,
        )

    ib = get_ibkr_client()
    contracts, sides = build_calendar_contracts(req)
    qualified = ib.qualify_contracts(contracts)

    legs: List[ComboLeg] = []
    for c, side in zip(qualified, sides):
        legs.append(make_combo_leg(c.conId, ratio=1, order_side=side))

    combo = Contract()
    combo.symbol = req.symbol
    combo.secType = "BAG"
    combo.currency = "USD"
    combo.exchange = "SMART"
    combo.comboLegs = legs

    is_buy = True
    order_ids = ib.place_combo_order(combo, legs, total_quantity=req.quantity, is_buy=is_buy)

    return OrderResult(
        success=True,
        order_ids=order_ids,
        message="Calendar spread submitted",
        risk=risk,
        spread_type=SpreadType.CALENDAR,
    )
