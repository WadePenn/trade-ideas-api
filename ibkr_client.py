# ibkr_client.py
import time
from threading import Thread
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract


class IBKR(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

        # Storage for real-time data
        self.market_data = {}
        self.bid = {}
        self.ask = {}
        self.last = {}
        self.iv = {}
        self.delta = {}
        self.gamma = {}
        self.vega = {}
        self.theta = {}

        # Storage for positions and orders
        self.positions_data = []
        self.orders_data = []

    # -----------------------------
    # POSITIONS
    # -----------------------------
    def position(self, account, contract, position, avgCost):
        self.positions_data.append({
            "symbol": contract.symbol,
            "qty": position,
            "avgCost": avgCost
        })

    def positionEnd(self):
        pass

    # -----------------------------
    # ORDERS
    # -----------------------------
    def openOrder(self, orderId, contract, order, orderState):
        self.orders_data.append({
            "id": orderId,
            "symbol": contract.symbol,
            "status": orderState.status
        })

    # -----------------------------
    # MARKET DATA
    # -----------------------------
    def tickPrice(self, reqId, tickType, price, attrib):
        if tickType == 1:      # BID
            self.bid[reqId] = price
        elif tickType == 2:    # ASK
            self.ask[reqId] = price
        elif tickType == 4:    # LAST
            self.last[reqId] = price

        self.market_data[reqId] = {
            "bid": self.bid.get(reqId),
            "ask": self.ask.get(reqId),
            "last": self.last.get(reqId),
            "iv": self.iv.get(reqId),
        }

    def tickOptionComputation(self, reqId, tickType, impliedVol, delta, optPrice,
                              pvDividend, gamma, vega, theta, undPrice):
        if impliedVol > 0:
            self.iv[reqId] = impliedVol

        self.delta[reqId] = delta
        self.gamma[reqId] = gamma
        self.vega[reqId] = vega
        self.theta[reqId] = theta

    # -----------------------------
    # CONNECTION MANAGEMENT
    # -----------------------------
    def start(self):
        if not self.isConnected():
            self.connect("127.0.0.1", 7497, clientId=1)
            thread = Thread(target=self.run, daemon=True)
            thread.start()
            time.sleep(1)


ibkr = IBKR()


# -----------------------------
# CONTRACT HELPERS
# -----------------------------
def stock_contract(symbol: str):
    c = Contract()
    c.symbol = symbol
    c.secType = "STK"
    c.currency = "USD"
    c.exchange = "SMART"
    return c


# -----------------------------
# REAL-TIME SNAPSHOT
# -----------------------------
def get_snapshot(symbol: str):
    ibkr.start()

    req_id = hash(symbol) % 10000  # stable unique ID per symbol

    contract = stock_contract(symbol)

    # Request market data
    ibkr.reqMktData(req_id, contract, "100,101,104,106", False, False, [])

    time.sleep(1)  # allow data to populate

    md = ibkr.market_data.get(req_id, {})

    return {
        "symbol": symbol,
        "bid": md.get("bid"),
        "ask": md.get("ask"),
        "last": md.get("last"),
        "iv": md.get("iv"),
    }
from ibapi.common import BarData

# storage for historical bars
ibkr.bars = {}

def get_bars(symbol: str, duration: str = "5 D", bar_size: str = "15 mins"):
    ibkr.start()

    req_id = (hash(symbol) % 8000) + 1000
    ibkr.bars[req_id] = []

    contract = stock_contract(symbol)

    ibkr.reqHistoricalData(
        req_id,
        contract,
        "",
        duration,
        bar_size,
        "TRADES",
        1,
        1,
        False,
        []
    )

    time.sleep(2)

    return ibkr.bars.get(req_id, [])
    def historicalData(self, reqId: int, bar: BarData):
        if not hasattr(self, "bars"):
            self.bars = {}
        if reqId not in self.bars:
            self.bars[reqId] = []
        self.bars[reqId].append({
            "time": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        })

