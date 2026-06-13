"""events_bridge.py — Uniform EventBus shim + event name constants."""
from __future__ import annotations
import logging
from typing import Callable, Optional

log = logging.getLogger("trade_ideas.events")

EV_IDEAS_UPDATED   = "trade_ideas_updated"
EV_IDEA_SELECTED   = "trade_idea_selected"
EV_IBKR_SENT       = "ibkr_order_sent"
EV_IBKR_STATUS     = "ibkr_status_changed"
EV_THEME_CHANGED   = "theme_changed"
EV_SYMBOL_SELECTED = "symbol_selected"
EV_MARKET_DATA     = "market_data"


class EventBusShim:
    """Detects .subscribe/.publish, .on/.emit, .listen/.dispatch, .add_listener/.fire"""
    def __init__(self, bus):
        self._bus = bus
        self._sub, self._pub = self._detect(bus)

    @staticmethod
    def _detect(bus):
        if hasattr(bus,"subscribe") and hasattr(bus,"publish"):
            return bus.subscribe, bus.publish
        if hasattr(bus,"on") and hasattr(bus,"emit"):
            return bus.on, bus.emit
        if hasattr(bus,"listen") and hasattr(bus,"dispatch"):
            return bus.listen, bus.dispatch
        if hasattr(bus,"add_listener") and hasattr(bus,"fire"):
            return bus.add_listener, bus.fire
        log.warning("EventBus type '%s' has no recognised API — events silently discarded", type(bus).__name__)
        return (lambda e,cb: None), (lambda e,d=None: None)

    def subscribe(self, event: str, cb: Callable):
        try: self._sub(event, cb)
        except Exception as e: log.warning("subscribe(%s): %s", event, e)

    def publish(self, event: str, payload=None):
        try: self._pub(event, payload)
        except Exception as e: log.warning("publish(%s): %s", event, e)


def wrap_event_bus(bus) -> Optional[EventBusShim]:
    if bus is None: return None
    return bus if isinstance(bus, EventBusShim) else EventBusShim(bus)
