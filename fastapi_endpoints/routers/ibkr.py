"""
routers/ibkr.py — IBKR order endpoints for the Trade Ideas panel.

Routes:
  POST /ibkr/submit           — place a BAG combo order
  GET  /ibkr/order/{order_id} — poll order status
  POST /ibkr/cancel/{order_id}— cancel an order

In main.py:
    from routers.ibkr import router as ibkr_router
    app.include_router(ibkr_router)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path

from ..schemas.ibkr import (
    IBKRCancelResponse,
    IBKROrderStatusResponse,
    IBKRSubmitRequest,
    IBKRSubmitResponse,
    OrderStatus,
)
from ..services.ibkr_order_service import IBKROrderProvider, get_ibkr_order_service

log = logging.getLogger("fastapi_api.ibkr")

router = APIRouter(
    prefix="/ibkr",
    tags=["IBKR Orders"],
)


# ─────────────────────────────────────────────────────────────────
# POST /ibkr/submit
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/submit",
    response_model=IBKRSubmitResponse,
    status_code=200,
    summary="Submit a BAG combo order to IBKR",
    description=(
        "Accepts a multi-leg options combo (BAG) order built by the Trade Ideas "
        "ibkr_bridge and routes it to Interactive Brokers. "
        "Returns order_id immediately; poll /ibkr/order/{id} for fill status."
    ),
    responses={
        200: {"description": "Order submitted successfully"},
        400: {"description": "Invalid order payload"},
        422: {"description": "Validation error"},
        503: {"description": "IBKR not connected"},
    },
)
async def submit_order(
    req: IBKRSubmitRequest,
    service: IBKROrderProvider = Depends(get_ibkr_order_service),
) -> IBKRSubmitResponse:

    log.info(
        "Submit order: sym=%s action=%s qty=%d lmt=%.2f strat=%s legs=%d tag=%s",
        req.symbol, req.action, req.quantity, req.limit_price,
        req.strategy, len(req.legs), req.client_tag,
    )

    if not req.legs:
        raise HTTPException(status_code=400, detail="Order must have at least one leg")

    try:
        result = service.submit(req)
        log.info(
            "Order accepted: id=%d acct=%s status=%s",
            result.order_id, result.account, result.status,
        )
        return result

    except ConnectionError as exc:
        log.error("IBKR not connected: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"IBKR not connected: {exc}",
        )

    except ValueError as exc:
        log.warning("Invalid order: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:
        log.exception("Unexpected error submitting order")
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────
# GET /ibkr/order/{order_id}
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/order/{order_id}",
    response_model=IBKROrderStatusResponse,
    summary="Poll status of a submitted order",
    description=(
        "Returns the current status of an IBKR order: "
        "SUBMITTED, FILLED, CANCELLED, or INACTIVE. "
        "The Trade Ideas panel polls this endpoint every 3 seconds after a send."
    ),
    responses={
        200: {"description": "Order status"},
        404: {"description": "Order ID not found"},
    },
)
async def get_order_status(
    order_id: int = Path(..., title="IBKR Order ID", ge=1),
    service:  IBKROrderProvider = Depends(get_ibkr_order_service),
) -> IBKROrderStatusResponse:

    log.debug("Status poll for order_id=%d", order_id)

    try:
        result = service.get_status(order_id)
    except Exception as exc:
        log.exception("Error fetching status for order_id=%d", order_id)
        raise HTTPException(status_code=500, detail=str(exc))

    if result.status == OrderStatus.INACTIVE and result.message == "Order not found":
        raise HTTPException(
            status_code=404,
            detail=f"Order {order_id} not found",
        )

    return result


# ─────────────────────────────────────────────────────────────────
# POST /ibkr/cancel/{order_id}
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/cancel/{order_id}",
    response_model=IBKRCancelResponse,
    summary="Cancel an IBKR order",
    description=(
        "Sends a cancel request for the given order. "
        "Returns status=CANCELLED on success, or the current status "
        "if the order cannot be cancelled (e.g., already FILLED)."
    ),
    responses={
        200: {"description": "Cancel result"},
        404: {"description": "Order ID not found"},
        409: {"description": "Order already filled or in non-cancellable state"},
    },
)
async def cancel_order(
    order_id: int = Path(..., title="IBKR Order ID", ge=1),
    service:  IBKROrderProvider = Depends(get_ibkr_order_service),
) -> IBKRCancelResponse:

    log.info("Cancel request for order_id=%d", order_id)

    try:
        result = service.cancel(order_id)
    except Exception as exc:
        log.exception("Error cancelling order_id=%d", order_id)
        raise HTTPException(status_code=500, detail=str(exc))

    if result.status == OrderStatus.INACTIVE and "not found" in result.message.lower():
        raise HTTPException(
            status_code=404,
            detail=f"Order {order_id} not found",
        )

    if result.status == OrderStatus.FILLED:
        raise HTTPException(
            status_code=409,
            detail=f"Order {order_id} already filled — cannot cancel",
        )

    return result
