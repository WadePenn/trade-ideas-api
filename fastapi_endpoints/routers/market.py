"""
routers/market.py — GET /market/snapshot/{symbol}

Drop this file into your FastAPI project, then in main.py:
    from routers.market import router as market_router
    app.include_router(market_router)
"""
from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from ..schemas.market import MarketSnapshotResponse, MarketSnapshotError
from ..services.market_data_service import MarketDataService, get_market_data_service

log = logging.getLogger("fastapi_api.market")

router = APIRouter(
    prefix="/market",
    tags=["Market Data"],
)

# ─────────────────────────────────────────────────────────────────
# Symbol validation helpers
# ─────────────────────────────────────────────────────────────────

_INVALID_CHARS = set("!@#$%^&*()+=[]{}|\\<>,?/\"';: ")

def _validate_symbol(symbol: str) -> str:
    sym = symbol.strip().upper()
    if not sym:
        raise HTTPException(status_code=400, detail="Symbol cannot be empty")
    if len(sym) > 10:
        raise HTTPException(status_code=400, detail=f"Symbol too long: {sym!r}")
    if any(c in _INVALID_CHARS for c in sym):
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {sym!r}")
    return sym


# ─────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/snapshot/{symbol}",
    response_model=MarketSnapshotResponse,
    summary="Market snapshot for Trade Ideas panel",
    description=(
        "Returns current price, IV30, HV20, IV Rank, IV Percentile, and "
        "recent price history for the given ticker symbol. "
        "Used by the Trade Ideas panel to score strategies."
    ),
    responses={
        200: {"description": "Snapshot data"},
        400: {"model": MarketSnapshotError, "description": "Bad symbol"},
        404: {"model": MarketSnapshotError, "description": "Symbol not found / no data"},
        503: {"model": MarketSnapshotError, "description": "Data provider unavailable"},
    },
)
async def get_market_snapshot(
    symbol: str = Path(
        ...,
        title="Ticker Symbol",
        description="US equity ticker, e.g. SPY, QQQ, AAPL",
        min_length=1,
        max_length=10,
    ),
    service: MarketDataService = Depends(get_market_data_service),
) -> MarketSnapshotResponse:
    sym = _validate_symbol(symbol)
    log.info("GET /market/snapshot/%s", sym)

    try:
        data = service.get_snapshot(sym)
        return MarketSnapshotResponse(**data)

    except ValueError as exc:
        # Symbol not found or no price data
        log.warning("Snapshot 404 for %s: %s", sym, exc)
        raise HTTPException(
            status_code=404,
            detail={"symbol": sym, "error": "Not found", "detail": str(exc)},
        )

    except RuntimeError as exc:
        # Data provider unavailable (yfinance offline, IBKR disconnected, etc.)
        log.error("Snapshot 503 for %s: %s", sym, exc)
        raise HTTPException(
            status_code=503,
            detail={"symbol": sym, "error": "Provider unavailable", "detail": str(exc)},
        )

    except Exception as exc:
        log.exception("Unexpected error fetching snapshot for %s", sym)
        raise HTTPException(
            status_code=500,
            detail={"symbol": sym, "error": "Internal error", "detail": str(exc)},
        )


# ─────────────────────────────────────────────────────────────────
# Optional: batch snapshot endpoint (not used by panel, useful for scanning)
# ─────────────────────────────────────────────────────────────────

from typing import List
from pydantic import BaseModel

class BatchSnapshotRequest(BaseModel):
    symbols: List[str]

class BatchSnapshotResponse(BaseModel):
    results: List[MarketSnapshotResponse]
    errors:  List[MarketSnapshotError]


@router.post(
    "/snapshots/batch",
    response_model=BatchSnapshotResponse,
    summary="Batch market snapshots (up to 20 symbols)",
    tags=["Market Data"],
)
async def get_batch_snapshots(
    request: BatchSnapshotRequest,
    service: MarketDataService = Depends(get_market_data_service),
) -> BatchSnapshotResponse:
    if len(request.symbols) > 20:
        raise HTTPException(status_code=400, detail="Max 20 symbols per batch request")

    results: list[MarketSnapshotResponse] = []
    errors:  list[MarketSnapshotError]    = []

    for raw_sym in request.symbols:
        try:
            sym  = _validate_symbol(raw_sym)
            data = service.get_snapshot(sym)
            results.append(MarketSnapshotResponse(**data))
        except HTTPException as he:
            errors.append(MarketSnapshotError(
                symbol=raw_sym.upper(),
                error=str(he.detail),
            ))
        except Exception as exc:
            errors.append(MarketSnapshotError(
                symbol=raw_sym.upper(),
                error=str(exc),
            ))

    return BatchSnapshotResponse(results=results, errors=errors)
