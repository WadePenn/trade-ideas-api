from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

class IBKROptionsChain(EWrapper, EClient):
    def __init__(self, symbol: str):
        EClient.__init__(self, self)
        self.symbol = symbol
        self.underlying_conId = None
        self.chain_data = []
        self.chain_done = False

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
        self.chain_data.append({
            "exchange": exchange,
            "tradingClass": tradingClass,
            "multiplier": multiplier,
            "expirations": sorted(list(expirations)),
            "strikes": sorted(list(strikes)),
        })

    def securityDefinitionOptionParameterEnd(self, reqId):
        self.chain_done = True

def fetch_chain(symbol: str = "SPY", timeout: float = 5.0):
    app = IBKROptionsChain(symbol)
    app.connect("127.0.0.1", 7497, clientId=7)

    t = threading.Thread(target=app.run, daemon=True)
    t.start()

    start = time.time()
    while not app.chain_done and (time.time() - start) < timeout:
        time.sleep(0.1)

    app.disconnect()
    return app.chain_data
