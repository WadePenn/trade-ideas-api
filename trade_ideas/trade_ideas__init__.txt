"""trade_ideas package — non-GUI symbols always importable; Panel is lazy-loaded."""
from .models import TradeIdea, IdeaScore, Greeks, OptionLeg, StrategyType, Trend, IdeaStatus
from .strategy_engine import StrategyEngine
from .ibkr_bridge import IBKRBridge
from .api_adapter import TradeIdeasAPIAdapter, MockAPIClient
from .events_bridge import EventBusShim, wrap_event_bus
from .hotkey_adapter import HotkeyAdapter
from .logger_setup import get_logger

__version__ = "1.0.0"
__all__ = [
    "TradeIdea", "IdeaScore", "Greeks", "OptionLeg", "StrategyType", "Trend", "IdeaStatus",
    "StrategyEngine", "IBKRBridge",
    "TradeIdeasAPIAdapter", "MockAPIClient",
    "EventBusShim", "wrap_event_bus",
    "HotkeyAdapter", "get_logger",
    "TradeIdeasPanel",
]

def __getattr__(name):
    if name == "TradeIdeasPanel":
        from .panel import TradeIdeasPanel
        return TradeIdeasPanel
    raise AttributeError(f"module 'trade_ideas' has no attribute {name!r}")
