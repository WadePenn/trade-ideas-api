from ibapi.client import EClient
from ibapi.wrapper import EWrapper

class IBKR(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId):
        print("Connected. Next Order ID:", orderId)

def connect_ibkr():
    app = IBKR()
    app.connect("127.0.0.1", 7497, clientId=1)
    app.run()

if __name__ == "__main__":
    connect_ibkr()
