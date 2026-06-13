from typing import List
from .config import settings
from .enums import SpreadType
from .models import RiskCheckResult

def check_spread_width(width: float, spread_type: SpreadType) -> RiskCheckResult:
    if width < 0:
        return RiskCheckResult(ok=False, reason="Negative width")
    if width > settings.max_spread_width:
        return RiskCheckResult(
            ok=False,
            reason=f"{spread_type.value} width {width} exceeds max {settings.max_spread_width}"
        )
    return RiskCheckResult(ok=True)

def check_notional_risk(per_contract_risk: float, quantity: int, spread_type: SpreadType) -> RiskCheckResult:
    total = per_contract_risk * quantity * 100.0
    if total > settings.max_notional_risk:
        return RiskCheckResult(
            ok=False,
            reason=f"{spread_type.value} notional {total} exceeds max {settings.max_notional_risk}"
        )
    return RiskCheckResult(ok=True)

def combine_checks(checks: List[RiskCheckResult]) -> RiskCheckResult:
    for c in checks:
        if not c.ok:
            return c
    return RiskCheckResult(ok=True)
