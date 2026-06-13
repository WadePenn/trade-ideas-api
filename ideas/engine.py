from typing import List, Dict
from .models import TradeIdea


def ema(values: List[float], length: int) -> float | None:
    if len(values) < length:
        return None
    k = 2 / (length + 1)
    ema_val = values[0]
    for v in values[1:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val


def compute_trend_from_bars(bars: List[Dict]) -> str:
    if len(bars) < 50:
        return "neutral"

    closes = [b["close"] for b in bars]
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)

    if ema20 is None or ema50 is None:
        return "neutral"

    if ema20 > ema50:
        return "up"
    if ema20 < ema50:
        return "down"
    return "neutral"


def simple_iv_rank(current_iv: float | None) -> float | None:
    if current_iv is None:
        return None
    # crude bucketing; replace with real IV history when ready
    # assume 0.1–0.8 typical range
    iv_low, iv_high = 0.10, 0.80
    v = max(min(current_iv, iv_high), iv_low)
    return (v - iv_low) / (iv_high - iv_low)


def score_symbol(snapshot: Dict) -> TradeIdea:
    symbol   = snapshot["symbol"]
    trend    = snapshot.get("trend", "neutral")
    iv_rank  = snapshot.get("iv_rank", None)
    iv_rank  = simple_iv_rank(iv_rank) if isinstance(iv_rank, (int, float)) else iv_rank

    direction = "wait"
    confidence = 0.4
    rr_ratio = 1.0
    notes = "No clear edge."

    # high IV + non‑downtrend → short premium
    if iv_rank is not None and iv_rank > 0.6 and trend in ("up", "neutral"):
        direction = "short_premium"
        confidence = 0.7
        rr_ratio = 1.8
        notes = "High IV + non‑bearish trend: consider defined‑risk credit spreads / condors."

    # uptrend + not high IV → long delta
    elif trend == "up":
        direction = "long_delta"
        confidence = 0.6
        rr_ratio = 1.4
        notes = "Uptrend: consider defined‑risk bullish structures."

    # downtrend + moderate/high IV → short delta
    elif trend == "down":
        direction = "short_delta"
        confidence = 0.6
        rr_ratio = 1.5
        notes = "Downtrend: consider defined‑risk bearish structures."

    return TradeIdea(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        rr_ratio=rr_ratio,
        notes=notes,
        trend=trend,
        iv_rank=iv_rank,
    )


def rank_trades(snapshots: List[Dict]) -> List[TradeIdea]:
    ideas = [score_symbol(s) for s in snapshots]
    ideas.sort(key=lambda x: (x.confidence, x.rr_ratio), reverse=True)
    return ideas
