from datetime import date
from ib_insync import Contract, ComboLeg
from .enums import OptionSide, OrderSide

def make_option_contract(symbol: str, expiry: date, strike: float, side: OptionSide) -> Contract:
    c = Contract()
    c.symbol = symbol
    c.secType = "OPT"
    c.exchange = "SMART"
    c.currency = "USD"
    c.lastTradeDateOrContractMonth = expiry.strftime("%Y%m%d")
    c.strike = float(strike)
    c.right = "C" if side == OptionSide.CALL else "P"
    return c

def make_combo_leg(contract_id: int, ratio: int, order_side: OrderSide) -> ComboLeg:
    leg = ComboLeg()
    leg.conId = contract_id
    leg.ratio = ratio
    leg.action = "BUY" if order_side == OrderSide.BUY else "SELL"
    leg.exchange = "SMART"
    return leg
