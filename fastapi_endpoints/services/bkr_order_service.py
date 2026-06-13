"""
services/ibkr_order_service.py — IBKR order management service.

Pluggable: implement IBKROrderProvider to route to any backend.
Default providers:
  - IBKRDirectProvider  — routes via ib_insync (TWS/Gateway connection)
  - IBKRPassthroughProvider — stores orders locally, you poll separately
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional, Protocol

from ..schemas.ibkr import (
    IBKRSubmitRequest,
    IBKRSubmitResponse,
    IBKROrderStatusResponse,
    IBKRCancelResponse,
    OrderStatus,
)

log = logging.getLogger("fastapi_api.ibkr")


# ─────────────────────────────────────────────────────────────────
# Provider protocol
# ─────────────────────────────────────────────────────────────────

class IBKROrderProvider(Protocol):
    def submit(self, req: IBKRSubmitRequest) -> IBKRSubmitResponse: ...
    def get_status(self, order_id: int)    -> IBKROrderStatusResponse: ...
    def cancel(self, order_id: int)        -> IBKRCancelResponse: ...


# ─────────────────────────────────────────────────────────────────
# In-memory provider (default) — no live IBKR connection needed
# Stores orders in RAM; you can swap with IBKRDirectProvider below.
# ─────────────────────────────────────────────────────────────────

class InMemoryOrderProvider:
    """
    Simulates IBKR order lifecycle in RAM.
    Orders auto-fill after ~8 seconds to simulate a real fill cycle.
    Replace with IBKRDirectProvider when you have a live TWS connection.
    """

    def __init__(self, auto_fill_seconds: float = 8.0, default_account: str = "DU_DEMO"):
        self._orders: Dict[int, IBKROrderStatusResponse] = {}
        self._next_id = 10001
        self._lock    = threading.Lock()
        self._auto_fill = auto_fill_seconds
        self._account   = default_account

    def submit(self, req: IBKRSubmitRequest) -> IBKRSubmitResponse:
        with self._lock:
            oid = self._next_id
            self._next_id += 1
            acct = req.account or self._account

            self._orders[oid] = IBKROrderStatusResponse(
                order_id   = oid,
                status     = OrderStatus.SUBMITTED,
                filled_qty = 0,
                remaining  = req.quantity,
                avg_fill   = 0.0,
                message    = f"BAG {req.action} {req.quantity} {req.symbol} LMT {req.limit_price}",
            )
            log.info(
                "Order SUBMITTED id=%d sym=%s action=%s qty=%d lmt=%.2f strat=%s",
                oid, req.symbol, req.action, req.quantity, req.limit_price, req.strategy,
            )

            # Schedule auto-fill in background
            threading.Thread(
                target=self._auto_fill_order,
                args=(oid, req.quantity, req.limit_price),
                daemon=True,
            ).start()

            return IBKRSubmitResponse(
                order_id = oid,
                account  = acct,
                status   = OrderStatus.SUBMITTED,
            )

    def get_status(self, order_id: int) -> IBKROrderStatusResponse:
        with self._lock:
            rec = self._orders.get(order_id)
        if rec is None:
            return IBKROrderStatusResponse(
                order_id = order_id,
                status   = OrderStatus.INACTIVE,
                message  = "Order not found",
            )
        return rec

    def cancel(self, order_id: int) -> IBKRCancelResponse:
        with self._lock:
            rec = self._orders.get(order_id)
            if rec is None:
                return IBKRCancelResponse(
                    order_id = order_id,
                    status   = OrderStatus.INACTIVE,
                    message  = "Order not found",
                )
            if rec.status in (OrderStatus.FILLED,):
                return IBKRCancelResponse(
                    order_id = order_id,
                    status   = rec.status,
                    message  = "Cannot cancel — order already filled",
                )
            rec.status  = OrderStatus.CANCELLED
            rec.message = "Cancelled by user"

        log.info("Order CANCELLED id=%d", order_id)
        return IBKRCancelResponse(
            order_id = order_id,
            status   = OrderStatus.CANCELLED,
            message  = "Cancelled",
        )

    # ── internal ──────────────────────────────────────────────────

    def _auto_fill_order(self, order_id: int, qty: int, limit_price: float):
        time.sleep(self._auto_fill)
        with self._lock:
            rec = self._orders.get(order_id)
            if rec is None or rec.status != OrderStatus.SUBMITTED:
                return
            rec.status     = OrderStatus.FILLED
            rec.filled_qty = qty
            rec.remaining  = 0
            rec.avg_fill   = limit_price
            rec.message    = f"Filled {qty} @ {limit_price:.2f}"
        log.info("Order FILLED id=%d qty=%d avg=%.2f", order_id, qty, limit_price)


# ─────────────────────────────────────────────────────────────────
# IBKR direct provider — routes through ib_insync / TWS
# ─────────────────────────────────────────────────────────────────

class IBKRDirectProvider:
    """
    Routes orders through a live ib_insync connection.
    Install: pip install ib_insync
    Requires: TWS or IB Gateway running with API enabled.
    """

    def __init__(self, ib_connection, default_account: str = ""):
        self._ib      = ib_connection
        self._account = default_account
        self._orders: Dict[int, int] = {}   # our_id → IBKR permId

    def submit(self, req: IBKRSubmitRequest) -> IBKRSubmitResponse:
        from ib_insync import Contract, ComboLeg, Order

        # Build underlying BAG contract
        contract             = Contract()
        contract.symbol      = req.symbol
        contract.secType     = "BAG"
        contract.currency    = req.currency
        contract.exchange    = req.exchange

        # Build combo legs
        legs = []
        for leg in req.legs:
            cl = ComboLeg()
            # Resolve conId — you need a live lookup here
            # This is placeholder: replace with self._ib.qualifyContracts() logic
            cl.conId    = self._resolve_con_id(leg)
            cl.ratio    = leg.ratio
            cl.action   = leg.action.value
            cl.exchange = leg.exchange
            legs.append(cl)
        contract.comboLegs = legs

        # Build order
        order            = Order()
        order.action     = req.action.value
        order.totalQuantity = req.quantity
        order.orderType  = req.order_type.value
        order.lmtPrice   = req.limit_price
        order.tif        = req.tif.value
        order.account    = req.account or self._account

        trade = self._ib.placeOrder(contract, order)
        self._ib.sleep(1)   # let IBKR process

        oid  = trade.order.orderId
        acct = trade.order.account or self._account

        log.info("IBKR order placed: orderId=%d sym=%s", oid, req.symbol)

        return IBKRSubmitResponse(
            order_id = oid,
            account  = acct,
            status   = OrderStatus.SUBMITTED,
        )

    def get_status(self, order_id: int) -> IBKROrderStatusResponse:
        trades = self._ib.trades()
        for trade in trades:
            if trade.order.orderId == order_id:
                st = trade.orderStatus
                ibkr_status = st.status.upper()
                mapped = {
                    "SUBMITTED":  OrderStatus.SUBMITTED,
                    "PRESUBMITTED": OrderStatus.SUBMITTED,
                    "FILLED":     OrderStatus.FILLED,
                    "CANCELLED":  OrderStatus.CANCELLED,
                    "INACTIVE":   OrderStatus.INACTIVE,
                }.get(ibkr_status, OrderStatus.PENDING)

                return IBKROrderStatusResponse(
                    order_id   = order_id,
                    status     = mapped,
                    filled_qty = int(st.filled),
                    remaining  = int(st.remaining),
                    avg_fill   = float(st.avgFillPrice),
                    message    = st.whyHeld or "",
                )

        return IBKROrderStatusResponse(
            order_id = order_id,
            status   = OrderStatus.INACTIVE,
            message  = "Order not found in active trades",
        )

    def cancel(self, order_id: int) -> IBKRCancelResponse:
        trades = self._ib.trades()
        for trade in trades:
            if trade.order.orderId == order_id:
                self._ib.cancelOrder(trade.order)
                self._ib.sleep(1)
                log.info("Cancel sent for IBKR orderId=%d", order_id)
                return IBKRCancelResponse(
                    order_id = order_id,
                    status   = OrderStatus.CANCELLED,
                    message  = "Cancel request sent",
                )
        return IBKRCancelResponse(
            order_id = order_id,
            status   = OrderStatus.INACTIVE,
            message  = "Order not found",
        )

    def _resolve_con_id(self, leg) -> int:
        """
        Look up the option contract conId via TWS.
        Replace with your existing contract-resolution logic.
        """
        from ib_insync import Option
        # Normalise expiry format: YYYY-MM-DD → YYYYMMDD
        expiry = leg.expiry.replace("-", "")
        opt = Option(
            symbol   = leg.symbol,
            lastTradeDateOrContractMonth = expiry,
            strike   = leg.strike,
            right    = leg.right,
            exchange = leg.exchange,
            currency = leg.currency,
        )
        contracts = self._ib.qualifyContracts(opt)
        if not contracts:
            raise ValueError(f"Cannot resolve contract: {leg}")
        return contracts[0].conId


# ─────────────────────────────────────────────────────────────────
# Singleton service
# ─────────────────────────────────────────────────────────────────

_provider: Optional[IBKROrderProvider] = None


def get_ibkr_order_service() -> IBKROrderProvider:
    global _provider
    if _provider is None:
        _provider = InMemoryOrderProvider()
        log.info("IBKROrderService initialised with InMemoryOrderProvider (demo mode)")
    return _provider


def init_ibkr_order_service(provider: IBKROrderProvider) -> None:
    global _provider
    _provider = provider
    log.info("IBKROrderService initialised with %s", type(provider).__name__)
