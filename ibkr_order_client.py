from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import threading
import time

# ---- RISK LIMITS (TUNE THESE) ----
MAX_ORDER_NOTIONAL = 5000.0   # max $ per order
MAX_QTY_PER_ORDER  = 200      # max shares per order

class IBKROrderClient(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.next_order_id = None

    def nextValidId(self, orderId):
        self.next_order_id = orderId

def _build_stock_contract(symbol: str) -> Contract:
    c = Contract()
    c.symbol = symbol
    c.secType = "STK"
    c.exchange = "SMART"
    c.currency = "USD"
    return c

def _build_limit_order(action: str, quantity: int, limit_price: float) -> Order:
    o = Order()
    o.action = action.upper()
    o.orderType = "LMT"
    o.totalQuantity = quantity
    o.lmtPrice = limit_price
    o.tif = "DAY"
    o.eTradeOnly = False
    o.firmQuoteOnly = False
    return o

def validate_order_risk(symbol: str, side: str, quantity: int, limit_price: float):
    notional = quantity * limit_price
    if quantity <= 0:
        return False, f"Invalid quantity: {quantity}"
    if quantity > MAX_QTY_PER_ORDER:
        return False, f"Quantity {quantity} exceeds MAX_QTY_PER_ORDER={MAX_QTY_PER_ORDER}"
    if notional > MAX_ORDER_NOTIONAL:
        return False, f"Notional ${notional:.2f} exceeds MAX_ORDER_NOTIONAL=${MAX_ORDER_NOTIONAL:.2f}"
    return True, "OK"

def submit_stock_limit_order(symbol: str, side: str, quantity: int, limit_price: float):
    ok, msg = validate_order_risk(symbol, side, quantity, limit_price)
    if not ok:
        return {"status": "rejected_risk", "reason": msg}

    app = IBKROrderClient()
    app.connect("127.0.0.1", 7497, clientId=8)

    t = threading.Thread(target=app.run, daemon=True)
    t.start()

    # wait for nextValidId
    start = time.time()
    while app.next_order_id is None and time.time() - start < 5:
        time.sleep(0.1)

    if app.next_order_id is None:
        app.disconnect()
        return {"status": "error", "reason": "No nextValidId received from IBKR"}

    contract = _build_stock_contract(symbol)
    order = _build_limit_order(side.upper(), quantity, limit_price)

    order_id = app.next_order_id
    app.placeOrder(order_id, contract, order)

    # small delay to let IBKR accept the order
    time.sleep(1)
    app.disconnect()

    return {
        "status": "submitted",
        "orderId": order_id,
        "symbol": symbol,
        "side": side.upper(),
        "quantity": quantity,
        "limit_price": limit_price,
        "notional": quantity * limit_price,
    }
