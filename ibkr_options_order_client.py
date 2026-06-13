from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import threading
import time

# ---- RISK LIMITS ----
MAX_OPTION_NOTIONAL = 5000.0
MAX_CONTRACTS_PER_ORDER = 20

class IBKROptionsOrderClient(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.next_order_id = None

    def nextValidId(self, orderId):
        self.next_order_id = orderId

def _build_option_contract(symbol: str, right: str, strike: float, expiry: str) -> Contract:
    c = Contract()
    c.symbol = symbol
    c.secType = "OPT"
    c.exchange = "SMART"
    c.currency = "USD"
    c.lastTradeDateOrContractMonth = expiry
    c.strike = float(strike)
    c.right = right.upper()
    c.multiplier = "100"
    return c

def _build_limit_order(action: str, quantity: int, limit_price: float) -> Order:
    o = Order()
    o.action = action.upper()
    o.orderType = "LMT"
    o.totalQuantity = quantity
    o.lmtPrice = limit_price
    o.tif = "DAY"
    return o

def validate_option_order_risk(symbol: str, side: str, quantity: int, limit_price: float):
    notional = quantity * limit_price * 100.0
    if quantity <= 0:
        return False, f"Invalid quantity: {quantity}"
    if quantity > MAX_CONTRACTS_PER_ORDER:
        return False, f"Quantity {quantity} exceeds MAX_CONTRACTS_PER_ORDER={MAX_CONTRACTS_PER_ORDER}"
    if notional > MAX_OPTION_NOTIONAL:
        return False, f"Notional ${notional:.2f} exceeds MAX_OPTION_NOTIONAL=${MAX_OPTION_NOTIONAL:.2f}"
    return True, "OK"

def submit_option_limit_order(
    symbol: str,
    side: str,
    right: str,
    strike: float,
    expiry: str,
    quantity: int,
    limit_price: float,
):
    ok, msg = validate_option_order_risk(symbol, side, quantity, limit_price)
    if not ok:
        return {"status": "rejected_risk", "reason": msg}

    app = IBKROptionsOrderClient()
    app.connect("127.0.0.1", 7497, clientId=9)

    t = threading.Thread(target=app.run, daemon=True)
    t.start()

    start = time.time()
    while app.next_order_id is None and time.time() - start < 5:
        time.sleep(0.1)

    if app.next_order_id is None:
        app.disconnect()
        return {"status": "error", "reason": "No nextValidId received from IBKR"}

    contract = _build_option_contract(symbol, right, strike, expiry)
    order = _build_limit_order(side, quantity, limit_price)

    order_id = app.next_order_id
    app.placeOrder(order_id, contract, order)

    time.sleep(1)
    app.disconnect()

    return {
        "status": "submitted",
        "orderId": order_id,
        "symbol": symbol,
        "side": side.upper(),
        "right": right.upper(),
        "strike": strike,
        "expiry": expiry,
        "quantity": quantity,
        "limit_price": limit_price,
        "notional": quantity * limit_price * 100.0,
    }
