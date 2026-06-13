"""
services/market_data_service.py — Market data service layer.

Fetches price history, computes HV20, IV30, IV Rank, IV Pct.
Pluggable source pattern — swap the data provider without changing the router.

Default provider: yfinance (pip install yfinance)
IBKR provider:    wire in your existing ib_insync / TWS connection.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Optional, Protocol

from .iv_service import compute_hv, compute_iv_rank, compute_iv_pct, estimate_iv_from_hv

log = logging.getLogger("fastapi_api.market")


# ─────────────────────────────────────────────────────────────────
# Provider protocol — implement either of these to swap data source
# ─────────────────────────────────────────────────────────────────

class MarketDataProvider(Protocol):
    """Implement this interface to plug in any data source."""

    def get_closes(self, symbol: str, days: int = 252) -> list[float]:
        """Return daily close prices, oldest first, length >= days."""
        ...

    def get_current_price(self, symbol: str) -> float:
        """Return last trade or mid price."""
        ...

    def get_iv30(self, symbol: str) -> Optional[float]:
        """
        Return 30-day constant-maturity implied vol (decimal).
        Return None if unavailable — service will estimate from HV.
        """
        ...

    def get_iv_history(self, symbol: str, days: int = 252) -> list[float]:
        """
        Return daily IV30 readings for IV Rank/Pct calculation.
        Return [] if unavailable — service will use HV-derived estimate.
        """
        ...


# ─────────────────────────────────────────────────────────────────
# yfinance provider (default, no API key required)
# ─────────────────────────────────────────────────────────────────

class YFinanceProvider:
    """
    Fetches price data via yfinance.
    IV30 is approximated from HV (yfinance does not supply option-model IV directly).
    For real IV, swap in your IBKR or Polygon provider below.
    Install: pip install yfinance
    """

    def __init__(self):
        try:
            import yfinance as yf
            self._yf = yf
            log.info("YFinanceProvider ready")
        except ImportError:
            raise RuntimeError(
                "yfinance not installed. Run: pip install yfinance\n"
                "Or wire in IBKRProvider / PolygonProvider instead."
            )

    def get_closes(self, symbol: str, days: int = 300) -> list[float]:
        ticker = self._yf.Ticker(symbol)
        hist   = ticker.history(period=f"{days}d", interval="1d", auto_adjust=True)
        if hist.empty:
            raise ValueError(f"No price history for {symbol}")
        return [round(float(p), 4) for p in hist["Close"].dropna().tolist()]

    def get_current_price(self, symbol: str) -> float:
        ticker = self._yf.Ticker(symbol)
        info   = ticker.fast_info
        price  = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
        if price is None:
            closes = self.get_closes(symbol, days=5)
            price  = closes[-1] if closes else 0.0
        return round(float(price), 4)

    def get_iv30(self, symbol: str) -> Optional[float]:
        # yfinance exposes implied volatility via options chain
        try:
            ticker = self._yf.Ticker(symbol)
            dates  = ticker.options
            if not dates:
                return None
            # Use expiry nearest to 30 DTE
            today    = datetime.utcnow().date()
            target   = today + timedelta(days=30)
            nearest  = min(dates, key=lambda d: abs((datetime.strptime(d, "%Y-%m-%d").date() - target).days))
            chain    = ticker.option_chain(nearest)
            calls    = chain.calls
            if calls.empty:
                return None
            # ATM IV from call nearest to current price
            price = self.get_current_price(symbol)
            atm   = calls.iloc[(calls["strike"] - price).abs().argsort()[:1]]
            iv    = float(atm["impliedVolatility"].iloc[0])
            return round(iv, 4) if iv > 0 else None
        except Exception as e:
            log.debug("IV30 fetch failed for %s: %s", symbol, e)
            return None

    def get_iv_history(self, symbol: str, days: int = 252) -> list[float]:
        # yfinance does not provide historical IV — return [] to trigger HV fallback
        return []


# ─────────────────────────────────────────────────────────────────
# IBKR provider stub — wire in your existing ib_insync connection
# ─────────────────────────────────────────────────────────────────

class IBKRProvider:
    """
    Wraps your existing ib_insync / TWS connection.
    Fill in each method with your existing data-fetching calls.
    """

    def __init__(self, ib_connection):
        """
        Parameters
        ----------
        ib_connection : your connected ib_insync.IB() instance
        """
        self._ib = ib_connection

    def get_closes(self, symbol: str, days: int = 300) -> list[float]:
        from ib_insync import Stock, util
        contract = Stock(symbol, "SMART", "USD")
        bars = self._ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=f"{days} D",
            barSizeSetting="1 day",
            whatToShow="ADJUSTED_LAST",
            useRTH=True,
        )
        return [round(float(b.close), 4) for b in bars]

    def get_current_price(self, symbol: str) -> float:
        from ib_insync import Stock
        contract = Stock(symbol, "SMART", "USD")
        tickers  = self._ib.reqTickers(contract)
        if tickers:
            mid = (tickers[0].bid + tickers[0].ask) / 2
            return round(float(mid), 4)
        return 0.0

    def get_iv30(self, symbol: str) -> Optional[float]:
        # Return your IBKR option model IV here
        # Example: query front-month ATM option impliedVol from TWS
        return None  # TODO: implement with your existing IBKR option chain logic

    def get_iv_history(self, symbol: str, days: int = 252) -> list[float]:
        # Return daily IV30 readings if you store them
        return []  # TODO: read from your database or IBKR historical vol


# ─────────────────────────────────────────────────────────────────
# Main service — computes the full snapshot payload
# ─────────────────────────────────────────────────────────────────

class MarketDataService:
    """
    Orchestrates data fetching + computation.
    Inject any provider that satisfies MarketDataProvider.
    """

    def __init__(self, provider: MarketDataProvider):
        self._src = provider

    def get_snapshot(self, symbol: str) -> dict:
        """
        Returns a dict matching MarketSnapshotResponse exactly.
        Called by the /market/snapshot/{symbol} endpoint.
        """
        symbol = symbol.upper().strip()
        log.info("Snapshot request: %s", symbol)

        # 1. Price history (need 252 bars for IV Rank + 20-bar HV)
        closes = self._src.get_closes(symbol, days=300)
        if not closes:
            raise ValueError(f"No price data available for {symbol}")

        price = self._src.get_current_price(symbol)
        if price <= 0:
            price = closes[-1]

        # 2. Historical volatility (20-day)
        hv20 = compute_hv(closes, window=20)

        # 3. Implied volatility (30-day)
        iv30 = self._src.get_iv30(symbol)
        if iv30 is None or iv30 <= 0:
            # Estimate from HV when option chain data unavailable
            iv30 = estimate_iv_from_hv(hv20, hv_ratio=1.25)
            log.debug("%s: IV30 estimated from HV20 (%.4f → %.4f)", symbol, hv20, iv30)

        # 4. IV Rank and Percentile
        iv_hist = self._src.get_iv_history(symbol, days=252)
        if not iv_hist:
            # Build synthetic IV history from HV history as fallback
            iv_hist = _synthetic_iv_history(closes, hv_ratio=1.25)

        iv_rank = compute_iv_rank(iv30, iv_hist, lookback=252)
        iv_pct  = compute_iv_pct(iv30, iv_hist,  lookback=252)

        # 5. Price history for trend detection (last 20 closes)
        price_history = [round(float(c), 4) for c in closes[-20:]]

        return {
            "symbol":        symbol,
            "price":         round(price, 4),
            "iv30":          round(iv30,  4),
            "hv20":          round(hv20,  4),
            "iv_rank":       round(iv_rank, 1),
            "iv_pct":        round(iv_pct,  1),
            "price_history": price_history,
        }


# ─────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────

def _synthetic_iv_history(closes: list[float], hv_ratio: float = 1.25) -> list[float]:
    """
    Build a rolling 20-day HV series × hv_ratio when real IV history
    is unavailable, so IV Rank/Pct still give meaningful readings.
    """
    if len(closes) < 22:
        return []
    history = []
    for i in range(21, len(closes)):
        window = closes[i - 21: i]
        hv = compute_hv(window, window=20)
        history.append(round(hv * hv_ratio, 4))
    return history


# ─────────────────────────────────────────────────────────────────
# Singleton factory — called once at app startup
# ─────────────────────────────────────────────────────────────────

_service: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    """
    FastAPI dependency — returns the singleton service instance.
    Default: YFinanceProvider.
    To use IBKR: call init_market_data_service(IBKRProvider(your_ib)) at startup.
    """
    global _service
    if _service is None:
        _service = MarketDataService(YFinanceProvider())
    return _service


def init_market_data_service(provider: MarketDataProvider) -> None:
    """Call this in main.py startup to inject your preferred provider."""
    global _service
    _service = MarketDataService(provider)
    log.info("MarketDataService initialised with %s", type(provider).__name__)
