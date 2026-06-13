from typing import List
from ib_insync import Contract, ComboLeg

from .contracts import make_option_contract, make_combo_leg
from .enums import OrderSide, SpreadType
from .ibkr_client import get_ibkr_client
from .models import RollRequest, OrderResult
from .risk import check_notional_risk


def compute_roll_risk_per_contract() -> float:
    # Treat roll as 1x placeholder risk
    return 1.0


def execute_roll(req: RollRequest) -> OrderResult:
    per_contract_risk = compute_roll_risk_per_contract()
    risk = check_notional_risk(per_contract_risk, req.quantity, SpreadType.ROLL)

    if not risk.ok:
        return OrderResult(
            success=False,
            order_ids=[],
            message=risk.reason,
            risk=risk,
            spread_type=SpreadType.ROLL,
        )

    # Build current (closing) and target (opening) contracts
    current = make_option_contract(
        symbol=req.symbol,
        expiry=req.current_expiry,
        strike=req.current_strike,
        side=req.current_side,
    )
    target = make_option_contract(
        symbol=req.symbol,
        expiry=req.target_expiry,
        strike=req.target_strike,
        side=req.current_side,
    )

    # Roll logic: close current, open target
    current_side = OrderSide.BUY     # closing short
    target_side = OrderSide.SELL     # opening short

    ib = get_ibkr_client()
    qualified = ib.qualify_contracts([current, target])

    legs: List[ComboLeg] = []
    legs.append(make_combo_leg(qualified[0].conId, ratio=1, order_side=current_side))
    legs.append(make_combo_leg(qualified[1].conId, ratio=1, order_side=target_side))

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
        message="Roll submitted",
        risk=risk,
        spread_type=SpreadType.ROLL,
    )
