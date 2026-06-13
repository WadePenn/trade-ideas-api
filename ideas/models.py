from dataclasses import dataclass

@dataclass
class TradeIdea:
    symbol: str
    direction: str          # "long_delta", "short_premium", etc.
    confidence: float       # 0–1
    rr_ratio: float         # reward:risk estimate
    notes: str
    trend: str              # "up", "down", "neutral"
    iv_rank: float | None   # 0–1, or None if unavailable
