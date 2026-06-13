"""
services/iv_service.py — IV Rank, IV Percentile, and Historical Volatility calculators.

All pure-Python, no external deps beyond math/statistics.
Can be driven by any price/IV data source (IBKR, yfinance, Polygon, etc.)
"""
from __future__ import annotations

import math
import statistics
from typing import Optional


# ─────────────────────────────────────────────────────────────────
# Historical Volatility
# ─────────────────────────────────────────────────────────────────

def compute_hv(closes: list[float], window: int = 20, annualise: bool = True) -> float:
    """
    Compute close-to-close Historical Volatility over `window` bars.

    Parameters
    ----------
    closes    : list of daily close prices, oldest first
    window    : number of trading days to use (default 20)
    annualise : multiply by sqrt(252) to get annualised figure

    Returns
    -------
    float — HV as decimal (e.g. 0.20 = 20%)
    """
    if len(closes) < window + 1:
        window = len(closes) - 1
    if window < 2:
        return 0.0

    recent = closes[-(window + 1):]
    log_returns = [
        math.log(recent[i] / recent[i - 1])
        for i in range(1, len(recent))
        if recent[i - 1] > 0 and recent[i] > 0
    ]
    if len(log_returns) < 2:
        return 0.0

    stdev = statistics.stdev(log_returns)
    if annualise:
        stdev *= math.sqrt(252)
    return round(stdev, 6)


# ─────────────────────────────────────────────────────────────────
# IV Rank and Percentile
# ─────────────────────────────────────────────────────────────────

def compute_iv_rank(
    current_iv: float,
    iv_history:  list[float],
    lookback:    int = 252,
) -> float:
    """
    IV Rank = (current_iv - 52w_low) / (52w_high - 52w_low) * 100

    Parameters
    ----------
    current_iv  : today's implied vol (decimal)
    iv_history  : list of daily IV readings, oldest first
    lookback    : number of trading days for the range (default 252 = 1 year)

    Returns
    -------
    float 0–100
    """
    hist = iv_history[-lookback:] if len(iv_history) >= lookback else iv_history
    if not hist:
        return 50.0

    iv_low  = min(hist)
    iv_high = max(hist)

    if iv_high == iv_low:
        return 50.0

    rank = (current_iv - iv_low) / (iv_high - iv_low) * 100.0
    return round(min(max(rank, 0.0), 100.0), 1)


def compute_iv_pct(
    current_iv: float,
    iv_history:  list[float],
    lookback:    int = 252,
) -> float:
    """
    IV Percentile = fraction of days in the lookback where IV was BELOW current IV.

    Returns
    -------
    float 0–100
    """
    hist = iv_history[-lookback:] if len(iv_history) >= lookback else iv_history
    if not hist:
        return 50.0

    below = sum(1 for v in hist if v < current_iv)
    return round(below / len(hist) * 100.0, 1)


# ─────────────────────────────────────────────────────────────────
# IV30 approximation from option chain data
# ─────────────────────────────────────────────────────────────────

def interpolate_iv30(
    near_iv:  float,
    near_dte: int,
    far_iv:   float,
    far_dte:  int,
    target_dte: int = 30,
) -> float:
    """
    Linear interpolation of constant-30-day IV from two expirations.
    Used when you have near and far chain IVs but not exactly 30 DTE.

    Returns
    -------
    float — interpolated IV as decimal
    """
    if far_dte == near_dte:
        return near_iv
    weight = (target_dte - near_dte) / (far_dte - near_dte)
    weight = min(max(weight, 0.0), 1.0)
    iv = near_iv + weight * (far_iv - near_iv)
    return round(iv, 6)


# ─────────────────────────────────────────────────────────────────
# VIX-proxy HV/IV estimate when no chain data is available
# ─────────────────────────────────────────────────────────────────

def estimate_iv_from_hv(
    hv20:      float,
    hv_ratio:  float = 1.25,
) -> float:
    """
    Rough IV30 estimate when no option chain is available.
    IV tends to trade at a premium to HV (the vol risk premium).
    Default ratio: IV ≈ 1.25 × HV20.
    """
    return round(hv20 * hv_ratio, 4)
