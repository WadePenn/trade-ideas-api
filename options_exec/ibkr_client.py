from __future__ import annotations
from functools import lru_cache
from typing import List
from ib_insync import IB, Contract, ComboLeg, Order
from .config import settings

class IBKRClient:
    def __init__(self):
        self.ib = IB()

    def connect(self):
        if not self.ib.isConnected():
            self.ib.connect(
                host=settings.ib_host,
                port=settings.ib_port,
                clientId=settings.ib_client_id,
            )

    def qualify_contracts(self, contracts: List[Contract]) -> List[Contract]:
        self.connect()
        return list(self.ib.qualifyContracts(*contracts))

    def place_combo_order(
        self,
        contract: Contract,
        legs: list[ComboLeg],
        total_quantity: int,
        is_buy: bool,
        limit_price: float | None = None,
    ) -> List[int]:
        self.connect()
        contract.comboLegs = legs

        order = Order()
        order.action = "BUY" if is_buy else "SELL"
        order.totalQuantity = total_quantity
        order.orderType = "LMT" if limit_price else "MKT"
        if limit_price:
            order.lmtPrice = limit_price

        trade = self.ib.placeOrder(contract, order)
        self.ib.sleep(0.1)
        return [trade.order.orderId]

@lru_cache(maxsize=1)
def get_ibkr_client() -> IBKRClient:
    c = IBKRClient()
    c.connect()
    return c
