from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

class IBKROptionsGreeks(EWrapper, EClient):
    def __init__(self, symbol="SPY"):
        EClient.__init__(self, self)
        self.symbol = symbol
        self.underlying_conId = None
        self.stream_started = False
        self.latest_greeks = {}  # shared state

    def nextValidId(self, orderId):
        self.request_underlying_contract()

    def request_underlying_contract(self):
        c = Contract()
        c.symbol = self.symbol
        c.secType = "STK"
        c.exchange = "SMART"
        c.currency = "USD"
        self.reqContractDetails(9001, c)

    def contractDetails(self, reqId, details):
        self.underlying_conId = details.contract.conId

    def contractDetailsEnd(self, reqId):
        self.request_option_chain()

    def request_option_chain(self):
        self.reqSecDefOptParams(
            reqId=1001,
            underlyingSymbol=self.symbol,
            futFopExchange="",
            underlyingSecType="STK",
            underlyingConId=self.underlying_conId
        )

    def securityDefinitionOptionParameter(self, reqId, exchange, underlyingConId,
                                          tradingClass, multiplier, expirations, strikes):
        if self.stream_started:
            return
        exp = sorted(list(expirations))[0]
        strike = sorted(list(strikes))[len(strikes)//2]
        self.start_option_stream(exp, strike)
        self.stream_started = True

    def start_option_stream(self, expiration, strike):
        c = Contract()
        c.symbol = self.symbol
        c.secType = "OPT"
        c.currency = "USD"
        c.exchange = "SMART"
        c.lastTradeDateOrContractMonth = expiration
        c.strike = float(strike)
        c.right = "C"
        c.multiplier = "100"
        self.reqMktData(2001, c, "100,101,104,106", False, False, [])

    def tickOptionComputation(self, reqId, tickType, tickAttrib, impliedVol,
                              delta, optPrice, pvDividend, gamma, vega, theta, undPrice):
        self.latest_greeks = {
            "symbol": self.symbol,
            "reqId": reqId,
            "tickType": tickType,
            "iv": impliedVol,
            "delta": delta,
            "gamma": gamma,
            "theta": theta,
            "vega": vega,
            "optPrice": optPrice,
            "underlyingPrice": undPrice,
        }

def start_ibkr_greeks_client():
    app = IBKROptionsGreeks(symbol="SPY")
    app.connect("127.0.0.1", 7497, clientId=6)
    t = threading.Thread(target=app.run, daemon=True)
    t.start()
    # give it a moment to connect and start streaming
    time.sleep(2)
    return app

# singleton instance for FastAPI to use
ibkr_client = None

def get_ibkr_client():
    global ibkr_client
    if ibkr_client is None:
        ibkr_client = start_ibkr_greeks_client()
    return ibkr_client
