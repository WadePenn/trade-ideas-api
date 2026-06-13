from typing import Tuple, List
from ib_insync import Contract, ComboLeg

from .contracts import make_option_contract, make_combo_leg
from .enums import OptionSide, OrderSide, SpreadType
from .ibkr_client import get_ibkr_client
from .models import VerticalRequest, OrderResult
from .risk import check_spread_width, check_notional_risk, combine_checks


def compute_vertical_width(req: VerticalRequest) -> float:
    if req.side == OptionSide.CALL:
        return abs(req.long_strike - req.short_strike)
    else:
        return abs(req.short_strike - req.long_strike)


def compute_vertical_risk_per_contract(req: VerticalRequest, width: float) -> float:
    return width  # defined risk = width


def build_vertical_contracts(req: VerticalRequest) -> Tuple[List[Contract], List[OrderSide]]:
    short_contract = make_option_contract(
        symbol=req.symbol,
        expiry=req.expiry,
        strike=req.short_strike,
        side=req.side,
    )
    long_contract = make_option_contract(
        symbol=req.symbol,
        expiry=req.expiry,
        strike=req.long_strike,
        side=req.side,
    )

    if req.intent == "OPEN":
        short_side = OrderSide.SELL
        long_side = OrderSide.BUY
    else:
        short_side = OrderSide.BUY
        long_side = OrderSide.SELL

    return [short_contract, long_contract], [short_side, long_side]


def execute_vertical(req: VerticalRequest) -> OrderResult:
    width = compute_vertical_width(req)
    per_contract_risk = compute_vertical_risk_per_contract(req, width)

    checks = [
        check_spread_width(width, SpreadType.VERTICAL),
        check_notional_risk(per_contract_risk, req.quantity, SpreadType.VERTICAL),
    ]
    risk = combine_checks(checks)

    if not risk.ok:
        return OrderResult(
            success=False,
            order_ids=[],
            message=risk.reason,
            risk=risk,
            spread_type=SpreadType.VERTICAL,
        )

    ib = get_ibkr_client()
    contracts, sides = build_vertical_contracts(req)
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

    is_buy = True  # default net debit/credit handling
    order_ids = ib.place_combo_order(combo, legs, total_quantity=req.quantity, is_buy=is_buy)

    return OrderResult(
        success=True,
        order_ids=order_ids,
        message="Vertical spread submitted",
        risk=risk,
        spread_type=SpreadType.VERTICAL,
    )
