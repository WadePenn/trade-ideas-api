"""
routers/sell_premium.py — Sell Premium scan endpoints.

Routes:
  POST /sell-premium/scan              — run full 0/7 DTE credit spread scan
  GET  /sell-premium/chain/{symbol}    — return raw option chain for given DTE

In main.py:
    from fastapi_endpoints.routers.sell_premium import router as sp_router
    app.include_router(sp_router)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..schemas.sell_premium import (
    ChainResponse,
    SellPremiumScanRequest,
    SellPremiumScanResponse,
)
from ..services.sell_premium_service import (
    SellPremiumService,
    get_sell_premium_service,
)

log = logging.getLogger("fastapi_api.sell_premium")

router = APIRouter(
    prefix="/sell-premium",
    tags=["Sell Premium"],
)

_INVALID = set("!@#$%^&*()+=[]{}|\\<>,?/\"';: ")

def _validate_sym(sym: str) -> str:
    s = sym.strip().upper()
    if not s or len(s) > 10 or any(c in _INVALID for c in s):
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {sym!r}")
    return s


# ── POST /sell-premium/scan ───────────────────────────────────────

@router.post(
    "/scan",
    response_model=SellPremiumScanResponse,
    summary="0/7 DTE sell premium credit spread scanner",
    description=(
        "Scans for the best credit spreads (bull put / bear call) for "
        "0-day and/or 7-day expirations. Applies delta, credit, width, "
        "bid-ask, open interest, POP, and gamma filters. Returns spreads "
        "ranked by composite score."
    ),
    responses={
        200: {"description": "Scan results"},
        400: {"description": "Invalid symbol or request"},
        503: {"description": "Market data unavailable"},
    },
)
async def scan_sell_premium(
    req:     SellPremiumScanRequest,
    service: SellPremiumService = Depends(get_sell_premium_service),
) -> SellPremiumScanResponse:
    req.symbol = _validate_sym(req.symbol)
    log.info(
        "Sell premium scan: sym=%s dte_mode=%s contracts=%d",
        req.symbol, req.dte_mode, req.contracts,
    )
    try:
        result = service.scan(req)
        log.info(
            "Scan complete: %s %s — %d spreads found",
            req.symbol, req.dte_mode, result.total_found,
        )
        return result
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=f"Market data unavailable: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        log.exception("Sell premium scan error")
        raise HTTPException(status_code=500, detail="Internal scan error")


# ── GET /sell-premium/chain/{symbol} ─────────────────────────────

@router.get(
    "/chain/{symbol}",
    response_model=ChainResponse,
    summary="Option chain for a given symbol and DTE",
    description=(
        "Returns the full option chain (all strikes, both calls and puts) "
        "for the requested expiration. Used by the Trade Ideas panel's "
        "SellPremiumScanner to build and filter spreads client-side."
    ),
    responses={
        200: {"description": "Option chain data"},
        400: {"description": "Invalid symbol"},
        404: {"description": "No data for this expiry"},
        503: {"description": "Data provider unavailable"},
    },
)
async def get_chain(
    symbol:  str = Path(..., min_length=1, max_length=10, description="US equity ticker"),
    dte:     int = Query(7, ge=0, le=45, description="Days to expiration (0 or 7 recommended)"),
    service: SellPremiumService = Depends(get_sell_premium_service),
) -> ChainResponse:
    sym = _validate_sym(symbol)
    log.info("Chain request: sym=%s dte=%d", sym, dte)
    try:
        return service.get_chain(sym, dte)
    except Exception:
        log.exception("Chain fetch error")
        raise HTTPException(status_code=503, detail="Could not retrieve option chain")
