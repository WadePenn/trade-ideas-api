"""hotkey_adapter.py — Shim supporting multiple HotkeyManager API shapes."""
from __future__ import annotations
import logging
from typing import Callable

log = logging.getLogger("trade_ideas.hotkeys")

HOTKEYS = {
    "alt+r": "Trade Ideas: Scan / Refresh",
    "alt+s": "Trade Ideas: Send to IBKR",
    "f5":    "Trade Ideas: Force Refresh",
}

class HotkeyAdapter:
    """Supports .register, .bind, .add, .add_hotkey underlying APIs."""
    def __init__(self, mgr):
        self._mgr = mgr
        self._fn  = self._detect(mgr)

    @staticmethod
    def _detect(mgr):
        if hasattr(mgr, "register"):
            return lambda c,cb,desc="": mgr.register(c, cb, description=desc)
        if hasattr(mgr, "bind"):
            return lambda c,cb,desc="": mgr.bind(c, cb)
        if hasattr(mgr, "add"):
            return lambda c,cb,desc="": mgr.add(c, cb, label=desc)
        if hasattr(mgr, "add_hotkey"):
            return lambda c,cb,desc="": mgr.add_hotkey(c, cb)
        log.warning("HotkeyManager type '%s' has no recognised API", type(mgr).__name__)
        return None

    def register(self, combo: str, callback: Callable, description: str = ""):
        if self._fn is None:
            raise AttributeError("No supported register API found")
        try:
            self._fn(combo, callback, description)
        except Exception as e:
            log.warning("register(%s) failed: %s", combo, e)
            raise
