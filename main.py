# main.py — FastAPI entry point for the Trade Ideas backend.
#
# Wires together:
#   - market data endpoints  (/market/...)
#   - IBKR order endpoints   (/ibkr/...)
#   - sell-premium scanner   (/sell-premium/...)
#
# Run:
#   py -3.11 -m uvicorn main:app --reload
#
# Docs:
#   http://localhost:8000/docs

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── routers ─────────────────────────────────────────────────────────────────
from fastapi_endpoints.routers.market       import router as market_router
from fastapi_endpoints.routers.ibkr         import router as ibkr_router
from fastapi_endpoints.routers.sell_premium import router as sp_router

# ── service factories ────────────────────────────────────────────────────────
from fastapi_endpoints.services.market_data_service import (
    init_market_data_service,
    YFinanceProvider,
)
from fastapi_endpoints.services.ibkr_order_service import (
    init_ibkr_order_service,
    InMemoryOrderProvider,
)
from fastapi_endpoints.services.sell_premium_service import (
    SellPremiumService,
    init_sell_premium_service,
)

# ── IBKR direct provider (live TWS/Gateway) ───────────────────────────────────
# Imported here so it's available but NOT used until you flip the switch below.
try:
    from fastapi_endpoints.services.ibkr_direct_provider import IBKRDirectProvider
    _HAS_IBKR_DIRECT = True
except ImportError:
    _HAS_IBKR_DIRECT = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("trade_ideas.api")

# ════════════════════════════════════════════════════════════════════
# ██  IBKR CONNECTION SETTINGS — edit these to go live  ██
# ════════════════════════════════════════════════════════════════════
#
#   IBKR_LIVE = True   →  in-memory simulation (safe, no TWS needed)
#   IBKR_LIVE = True    →  real orders sent to TWS / IB Gateway
#
IBKR_LIVE      = True         # ← flip to True when ready
IBKR_HOST      = "127.0.0.1"
IBKR_PORT      = 7497           # TWS paper=7497  live=7496
                                 # Gateway paper=4002  live=4001
IBKR_CLIENT_ID = 1              # must differ from TWS's own client ID
# ════════════════════════════════════════════════════════════════════


# ── app ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Trade Ideas API",
    description=(
        "Market data + IBKR order routing + Sell Premium scanner "
        "for the Trade Ideas Tkinter panel."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── startup ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup() -> None:
    log.info("=== Trade Ideas API starting up ===")

    # Market data — yfinance (no API key required)
    init_market_data_service(YFinanceProvider())
    log.info("MarketDataService  → YFinanceProvider ready")

    # IBKR order routing
    if IBKR_LIVE and _HAS_IBKR_DIRECT:
        provider = IBKRDirectProvider(
            host      = IBKR_HOST,
            port      = IBKR_PORT,
            client_id = IBKR_CLIENT_ID,
        )
        if provider.connect():
            init_ibkr_order_service(provider)
            log.info(
                "IBKROrderService   → IBKRDirectProvider LIVE  (%s:%d)",
                IBKR_HOST, IBKR_PORT,
            )
        else:
            log.warning(
                "IBKRDirectProvider failed to connect — falling back to InMemoryOrderProvider"
            )
            init_ibkr_order_service(InMemoryOrderProvider())
    else:
        init_ibkr_order_service(InMemoryOrderProvider())
        mode = "IBKR_LIVE=True but ib_insync missing" if IBKR_LIVE else "IBKR_LIVE=False"
        log.info("IBKROrderService   → InMemoryOrderProvider  (%s)", mode)

    # Sell Premium scanner
    init_sell_premium_service(SellPremiumService())
    log.info("SellPremiumService → ready")

    log.info("=== Startup complete — listening ===")


@app.on_event("shutdown")
async def shutdown() -> None:
    # Disconnect from TWS cleanly if live
    try:
        from fastapi_endpoints.services.ibkr_order_service import get_ibkr_order_service
        svc = get_ibkr_order_service()
        if _HAS_IBKR_DIRECT and hasattr(svc, 'disconnect'):
            svc.disconnect()
    except Exception:
        pass
    log.info("=== Trade Ideas API shutting down ===")


# ── routers ──────────────────────────────────────────────────────────────────
app.include_router(market_router)   # /market/snapshot/{symbol}
app.include_router(ibkr_router)     # /ibkr/submit  /ibkr/order/{id}  /ibkr/cancel/{id}
app.include_router(sp_router)       # /sell-premium/scan  /sell-premium/chain/{symbol}


# ── root / health ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Root"], include_in_schema=False)
async def root():
    return {
        "service": "Trade Ideas API",
        "version": "1.0.0",
        "docs":    "/docs",
        "health":  "/health",
        "ibkr_live": IBKR_LIVE,
    }


@app.get("/health", tags=["Health"])
async def health():
    try:
        from fastapi_endpoints.services.ibkr_order_service import get_ibkr_order_service
        svc = get_ibkr_order_service()
        ic=getattr(svc,"is_connected",None);ibkr_connected=bool(ic()) if callable(ic) else bool(ic) if ic is not None else None
    except Exception:
        ibkr_connected = None
    return {
        "status":         "ok",
        "ibkr_live":      IBKR_LIVE,
        "ibkr_connected": ibkr_connected,
    }
