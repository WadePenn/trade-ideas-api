from typing import List, Tuple
from ib_insync import Contract, ComboLeg

from .contracts import make_option_contract, make_combo_leg
from .enums import OptionSide, OrderSide, SpreadType
from .ibkr_client import get_ibkr_client
from .models import IronCondorRequest, OrderResult
from .risk import check_spread_width, check_notional_risk, combine_checks


def compute_condor_widths(req: IronCondorRequest) -> Tuple[float, float]:
    call_width = abs(req.long_call_strike - req.short_call_strike)
    put_width = abs(req.short_put_strike - req.long_put_strike)
    return call_width, put_width


def compute_condor_risk_per_contract(req: IronCondorRequest) -> float:
    call_width, put_width = compute_condor_widths(req)
    return max(call_width, put_width)


def build_condor_contracts(req: IronCondorRequest) -> Tuple[List[Contract], List[OrderSide]]:
    short_call = make_option_contract(
        symbol=req.symbol,
        expiry=req.expiry,
        strike=req.short_call_strike,
        side=OptionSide.CALL,
    )
    long_call = make_option_contract(
        symbol=req.symbol,
        expiry=req.expiry,
        strike=req.long_call_strike,
        side=OptionSide.CALL,
    )
    short_put = make_option_contract(
        symbol=req.symbol,
        expiry=req.expiry,
        strike=req.short_put_strike,
        side=OptionSide.PUT,
    )
    long_put = make_option_contract(
        symbol=req.symbol,
        expiry=req.expiry,
        strike=req.long_put_strike,
        side=OptionSide.PUT,
    )

    if req.intent == "OPEN":
        sides = [
            OrderSide.SELL,  # short call
            OrderSide.BUY,   # long call
            OrderSide.SELL,  # short put
            OrderSide.BUY,   # long put
        ]
    else:
        sides = [
            OrderSide.BUY,
            OrderSide.SELL,
            OrderSide.BUY,
            OrderSide.SELL,
        ]

    return [short_call, long_call, short_put, long_put], sides


def execute_iron_condor(req: IronCondorRequest) -> OrderResult:
    call_width, put_width = compute_condor_widths(req)
    per_contract_risk = compute_condor_risk_per_contract(req)

    checks = [
        check_spread_width(call_width, SpreadType.IRON_CONDOR),
        check_spread_width(put_width, SpreadType.IRON_CONDOR),
        check_notional_risk(per_contract_risk, req.quantity, SpreadType.IRON_CONDOR),
    ]
    risk = combine_checks(checks)

    if not risk.ok:
        return OrderResult(
            success=False,
            order_ids=[],
            message=risk.reason,
            risk=risk,
            spread_type=SpreadType.IRON_CONDOR,
        )

    ib = get_ibkr_client()
    contracts, sides = build_condor_contracts(req)
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
        message="Iron condor submitted",
        risk=risk,
        spread_type=SpreadType.IRON_CONDOR,
    )
