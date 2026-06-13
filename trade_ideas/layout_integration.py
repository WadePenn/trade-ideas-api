"""
layout_integration.py — Plug TradeIdeasPanel into your existing layout.py.

Pattern A — Notebook tab (most common):
    from trade_ideas.layout_integration import register_trade_ideas_tab
    ti = register_trade_ideas_tab(notebook, api_client=..., ...)

Pattern B — Embed in any frame:
    from trade_ideas.layout_integration import create_trade_ideas_frame
    ti = create_trade_ideas_frame(parent, api_client=..., ...)
"""
from __future__ import annotations
import logging
from tkinter import ttk
from .panel import TradeIdeasPanel

log = logging.getLogger("trade_ideas.layout")


def register_trade_ideas_tab(
    notebook,
    api_client=None,
    event_bus=None,
    theme_manager=None,
    hotkey_mgr=None,
    app_logger=None,
    tab_label: str = "💡 Trade Ideas",
    dry_run: bool = True,
    refresh_interval: int = 60,
) -> TradeIdeasPanel:
    """Add a Trade Ideas tab to an existing ttk.Notebook. Returns the panel."""
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=tab_label)
    panel = _make(frame, api_client, event_bus, theme_manager,
                  hotkey_mgr, app_logger or log, dry_run, refresh_interval)
    log.info("Trade Ideas tab '%s' added", tab_label)
    return panel


def create_trade_ideas_frame(
    parent,
    api_client=None,
    event_bus=None,
    theme_manager=None,
    hotkey_mgr=None,
    app_logger=None,
    dry_run: bool = True,
    refresh_interval: int = 60,
    row: int = 0,
    col: int = 0,
    sticky: str = "nsew",
) -> TradeIdeasPanel:
    """Embed Trade Ideas panel directly into any parent frame. Returns the panel."""
    panel = _make(parent, api_client, event_bus, theme_manager,
                  hotkey_mgr, app_logger or log, dry_run, refresh_interval)
    panel.grid(row=row, column=col, sticky=sticky, padx=4, pady=4)
    return panel


def _make(parent, api_client, event_bus, theme_manager,
          hotkey_mgr, logger, dry_run, refresh_interval) -> TradeIdeasPanel:
    panel = TradeIdeasPanel(
        parent,
        api_client=api_client,
        event_bus=event_bus,
        theme_manager=theme_manager,
        hotkey_mgr=hotkey_mgr,
        app_logger=logger,
        dry_run=dry_run,
        refresh_interval=refresh_interval,
    )
    panel.pack(fill="both", expand=True)
    return panel
