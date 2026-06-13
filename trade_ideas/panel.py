# panel.py — TradeIdeasPanel: complete, self-contained Tkinter widget.
#
# Base class : tk.Frame  (NOT ttk.Frame — avoids -bg TclError)
# Fix 1      : isinstance(w, tk.Entry) and not isinstance(w, ttk.Widget)
#              guard in _apply_theme — prevents ttk.Spinbox -bg TclError
# Includes   : Sell Premium 0/7 DTE credit spread scanner
#
# Layout rows:
#   0  Controls   : Symbol | DTE | Qty | Mode | DTE Mode | DryRun | Acct
#   1  Strategies : Auto | Credit | Debit | Condor | Calendar | Sell Premium
#   2  Status bar : last refresh | trend | IV Rank | count | progress
#   3  Results    : 16-column sortable Treeview (expands)
#   4  Detail     : Score breakdown | Net Greeks | Legs
#   5  Actions    : Scan Now | Auto-Refresh | Copy | Cancel | Send to IBKR

from __future__ import annotations

import datetime
import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Optional

from .models import IdeaStatus, StrategyType, TradeIdea, Trend
from .strategy_engine import StrategyEngine
from .ibkr_bridge import IBKRBridge

log = logging.getLogger("trade_ideas.panel")

# ---------------------------------------------------------------------------
# Optional sell-premium import — graceful fallback if module absent
# ---------------------------------------------------------------------------
try:
    from .sell_premium_scanner import DTEMode, SellPremiumScanner
    _HAS_SP = True
except ImportError:
    _HAS_SP = False
    log.debug("sell_premium_scanner not found — Sell Premium button disabled")

# ---------------------------------------------------------------------------
# 16-column table definitions
# ---------------------------------------------------------------------------
COLUMNS = [
    ("id",         "ID",          55,  "center"),
    ("symbol",     "Symbol",      70,  "center"),
    ("strategy",   "Strategy",   125,  "w"),
    ("dte",        "DTE",         45,  "center"),
    ("score",      "Score",       58,  "center"),
    ("grade",      "Grade",       42,  "center"),
    ("pop",        "POP %",       60,  "center"),
    ("iv_rank",    "IV Rank",     65,  "center"),
    ("trend",      "Trend",       72,  "center"),
    ("net",        "Net",         82,  "center"),
    ("max_profit", "Max Profit",  88,  "center"),
    ("max_loss",   "Max Loss",    88,  "center"),
    ("delta",      "Delta",       65,  "center"),
    ("theta",      "Theta",       65,  "center"),
    ("vega",       "Vega",        65,  "center"),
    ("status",     "Status",      90,  "center"),
]

COL_FN = {
    "id":         lambda i: i.id,
    "symbol":     lambda i: i.symbol,
    "strategy":   lambda i: i.strategy.value,
    "dte":        lambda i: str(i.dte),
    "score":      lambda i: f"{i.score.composite:.1f}",
    "grade":      lambda i: i.score.grade,
    "pop":        lambda i: f"{i.pop:.1f}%",
    "iv_rank":    lambda i: f"{i.iv_rank:.1f}",
    "trend":      lambda i: i.trend.value,
    "net":        lambda i: f"${i.net_credit:+.2f}",
    "max_profit": lambda i: f"${i.max_profit:.2f}",
    "max_loss":   lambda i: f"${i.max_loss:.2f}",
    "delta":      lambda i: f"{i.net_greeks.delta:+.3f}",
    "theta":      lambda i: f"{i.net_greeks.theta:+.3f}",
    "vega":       lambda i: f"{i.net_greeks.vega:+.3f}",
    "status":     lambda i: i.status.value,
}

# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------
_DARK = {
    "bg":            "#1a1d23",
    "panel_bg":      "#20252e",
    "card_bg":       "#272c38",
    "border":        "#343a4a",
    "fg":            "#e0e4f0",
    "fg_muted":      "#7b8299",
    "accent":        "#4f8ef7",
    "accent_hover":  "#6fa3fa",
    "success":       "#2ecc71",
    "success_hover": "#3de084",
    "warning":       "#f39c12",
    "danger":        "#e74c3c",
    "danger_hover":  "#f15f50",
    "purple":        "#9b59b6",
    "score_ex":      "#2ecc71",
    "score_gd":      "#4f8ef7",
    "score_fair":    "#f39c12",
    "score_poor":    "#e74c3c",
    "entry_bg":      "#2a2f3d",
    "entry_fg":      "#e0e4f0",
    "btn_bg":        "#2a2f3d",
    "btn_fg":        "#e0e4f0",
    "btn_active":    "#343a4a",
    "sel_bg":        "#2c3a5a",
    "row_odd":       "#1e2330",
    "row_even":      "#20252e",
    "text_bg":       "#1e2330",
}

_LIGHT = {
    "bg":            "#f0f2f8",
    "panel_bg":      "#ffffff",
    "card_bg":       "#f7f8fc",
    "border":        "#d0d5e8",
    "fg":            "#1a1d23",
    "fg_muted":      "#5a6080",
    "accent":        "#2563eb",
    "accent_hover":  "#1d4ed8",
    "success":       "#16a34a",
    "success_hover": "#15803d",
    "warning":       "#d97706",
    "danger":        "#dc2626",
    "danger_hover":  "#b91c1c",
    "purple":        "#7c3aed",
    "score_ex":      "#16a34a",
    "score_gd":      "#2563eb",
    "score_fair":    "#d97706",
    "score_poor":    "#dc2626",
    "entry_bg":      "#ffffff",
    "entry_fg":      "#1a1d23",
    "btn_bg":        "#e8eaf0",
    "btn_fg":        "#1a1d23",
    "btn_active":    "#d0d5e8",
    "sel_bg":        "#dbeafe",
    "row_odd":       "#f7f8fc",
    "row_even":      "#ffffff",
    "text_bg":       "#f7f8fc",
}

# Fallback prices for offline/mock mode
_PRICES = {
    "SPY":  545.0, "QQQ":  480.0, "IWM":  215.0,
    "AAPL": 215.0, "TSLA": 310.0, "NVDA": 870.0,
    "AMZN": 195.0, "MSFT": 435.0,
}


# ---------------------------------------------------------------------------
# Tooltip helper
# ---------------------------------------------------------------------------
class _Tip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self._w   = widget
        self._txt = text
        self._win: Optional[tk.Toplevel] = None
        widget.bind("<Enter>",       self._show, add="+")
        widget.bind("<Leave>",       self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _=None) -> None:
        if self._win:
            return
        x = self._w.winfo_rootx() + 20
        y = self._w.winfo_rooty() + self._w.winfo_height() + 4
        self._win = tk.Toplevel(self._w)
        self._win.wm_overrideredirect(True)
        self._win.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._win, text=self._txt,
            background="#ffffe0", foreground="#000000",
            relief="solid", borderwidth=1,
            font=("Segoe UI", 8), padx=4, pady=2,
        ).pack()

    def _hide(self, _=None) -> None:
        if self._win:
            self._win.destroy()
            self._win = None


# ===========================================================================
# TradeIdeasPanel
# ===========================================================================
class TradeIdeasPanel(tk.Frame):
    """
    Main Trade Ideas panel widget.

    IMPORTANT: inherits from tk.Frame, NOT ttk.Frame.
    This prevents the TclError: unknown option "-bg" crash.
    """

    def __init__(
        self,
        parent,
        api_client=None,
        event_bus=None,
        theme_manager=None,
        hotkey_mgr=None,
        app_logger=None,
        dry_run: bool = True,
        refresh_interval: int = 60,
        **kw,
    ) -> None:
        super().__init__(parent, **kw)

        # --- dependencies ---------------------------------------------------
        self._api    = api_client
        self._bus    = event_bus
        self._theme  = theme_manager
        self._hkmgr  = hotkey_mgr
        self._log    = app_logger or log
        self._engine = StrategyEngine()
        self._bridge = IBKRBridge(
            api_client=api_client,
            dry_run=dry_run,
            on_status=self._on_ibkr_status,
        )
        self._refresh_interval = refresh_interval

        # --- state ----------------------------------------------------------
        self._ideas:     List[TradeIdea]      = []
        self._sel:       Optional[TradeIdea]  = None
        self._sort_col:  str  = "score"
        self._sort_desc: bool = True
        self._loading:   bool = False
        self._rjob:      Optional[str] = None   # after() handle
        self._cnt:       int  = 0
        self._dark_mode: bool = True

        # --- tk vars --------------------------------------------------------
        self._sym_var      = tk.StringVar(value="SPY")
        self._dte_var      = tk.IntVar(value=30)
        self._qty_var      = tk.IntVar(value=1)
        self._mode_var     = tk.StringVar(value="Auto")
        self._dte_mode_var = tk.StringVar(value="Both")
        self._dry_var      = tk.BooleanVar(value=dry_run)
        self._acct_var     = tk.StringVar(value="")
        self._auto_var     = tk.BooleanVar(value=False)
        self._status_var   = tk.StringVar(value="Ready")

        # --- build ----------------------------------------------------------
        self._build_ui()
        self._apply_theme()
        self._reg_events()
        self._reg_hotkeys()

    # =======================================================================
    # UI BUILD
    # =======================================================================

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)         # table row expands
        self._build_controls()                 # row 0
        self._build_strat_bar()                # row 1
        self._build_status_bar()               # row 2
        self._build_table()                    # row 3
        self._build_detail()                   # row 4
        self._build_actions()                  # row 5

    # --- row 0 : controls --------------------------------------------------
    def _build_controls(self) -> None:
        self._ctrl = tk.Frame(self, padx=6, pady=4)
        self._ctrl.grid(row=0, column=0, sticky="ew")

        def lbl(text: str) -> tk.Label:
            return tk.Label(self._ctrl, text=text, font=("Segoe UI", 8))

        # Symbol
        lbl("Symbol").pack(side="left", padx=(0, 2))
        sym_e = tk.Entry(
            self._ctrl, textvariable=self._sym_var,
            width=8, font=("Segoe UI", 10, "bold"),
        )
        sym_e.pack(side="left", padx=(0, 8))
        sym_e.bind("<Return>", lambda _: self._on_scan())
        _Tip(sym_e, "Ticker symbol, e.g. SPY, AAPL")

        # DTE
        lbl("DTE").pack(side="left", padx=(0, 2))
        dte_sb = ttk.Spinbox(
            self._ctrl, textvariable=self._dte_var,
            from_=0, to=365, width=5, font=("Segoe UI", 9),
        )
        dte_sb.pack(side="left", padx=(0, 8))
        _Tip(dte_sb, "Days to expiration target")

        # Qty
        lbl("Qty").pack(side="left", padx=(0, 2))
        qty_sb = ttk.Spinbox(
            self._ctrl, textvariable=self._qty_var,
            from_=1, to=100, width=4, font=("Segoe UI", 9),
        )
        qty_sb.pack(side="left", padx=(0, 8))
        _Tip(qty_sb, "Number of contracts")

        # Mode
        lbl("Mode").pack(side="left", padx=(0, 2))
        mode_cb = ttk.Combobox(
            self._ctrl, textvariable=self._mode_var,
            values=["Auto", "Credit", "Debit", "Condor", "Calendar"],
            state="readonly", width=10, font=("Segoe UI", 9),
        )
        mode_cb.pack(side="left", padx=(0, 8))
        mode_cb.bind("<<ComboboxSelected>>", self._on_mode_change)
        _Tip(mode_cb, "Strategy filter / auto-select best")

        # DTE Mode (sell premium filter)
        lbl("DTE Mode").pack(side="left", padx=(0, 2))
        dte_mode_cb = ttk.Combobox(
            self._ctrl, textvariable=self._dte_mode_var,
            values=["0 DTE", "7 DTE", "Both"],
            state="readonly", width=7, font=("Segoe UI", 9),
        )
        dte_mode_cb.pack(side="left", padx=(0, 8))
        _Tip(dte_mode_cb, "DTE filter used by Sell Premium scan")

        # Dry Run
        dry_cb = tk.Checkbutton(
            self._ctrl, text="Dry Run",
            variable=self._dry_var,
            font=("Segoe UI", 8),
            command=self._on_dry_toggle,
        )
        dry_cb.pack(side="left", padx=(0, 8))
        _Tip(dry_cb, "Simulate orders — nothing sent to IBKR")

        # Account
        lbl("Acct").pack(side="left", padx=(0, 2))
        acct_e = tk.Entry(
            self._ctrl, textvariable=self._acct_var,
            width=10, font=("Segoe UI", 9),
        )
        acct_e.pack(side="left", padx=(0, 4))
        _Tip(acct_e, "IB account number (blank = default)")

    # --- row 1 : strategy quick-buttons ------------------------------------
    def _build_strat_bar(self) -> None:
        self._sbar = tk.Frame(self, padx=6, pady=2)
        self._sbar.grid(row=1, column=0, sticky="ew")

        self._strat_btns: dict[str, tk.Button] = {}
        specs = [
            ("Auto",     "Auto (Best Fit)",   "#2e4a7a", self._on_scan),
            ("Credit",   "Credit Spread",     "#1e4a2e", lambda: self._quick("Credit")),
            ("Debit",    "Debit Spread",      "#4a3a1e", lambda: self._quick("Debit")),
            ("Condor",   "Iron Condor",       "#3a1e4a", lambda: self._quick("Condor")),
            ("Calendar", "Calendar",          "#1e3a4a", lambda: self._quick("Calendar")),
        ]
        for key, label, bg, cmd in specs:
            b = tk.Button(
                self._sbar, text=label, command=cmd,
                bg=bg, fg="#e0e4f0",
                activebackground="#3a4460", activeforeground="#ffffff",
                font=("Segoe UI", 9, "bold"),
                relief="flat", padx=10, pady=4, cursor="hand2",
            )
            b.pack(side="left", padx=3)
            self._strat_btns[key] = b

        # Sell Premium button — only shown when scanner module is present
        if _HAS_SP:
            sp_btn = tk.Button(
                self._sbar, text="Sell Premium (0/7 DTE)",
                command=self._on_sell_premium_scan,
                bg="#922b21", fg="#ffffff",
                activebackground="#b03a2e", activeforeground="#ffffff",
                font=("Segoe UI", 9, "bold"),
                relief="flat", padx=10, pady=4, cursor="hand2",
            )
            sp_btn.pack(side="left", padx=3)
            self._strat_btns["SellPremium"] = sp_btn
            _Tip(sp_btn, "Scan 0/7 DTE credit spreads for sell-premium setups")

    # --- row 2 : status bar ------------------------------------------------
    def _build_status_bar(self) -> None:
        self._sbar2 = tk.Frame(self, padx=6, pady=2)
        self._sbar2.grid(row=2, column=0, sticky="ew")

        self._lbl_last  = tk.Label(self._sbar2, text="Last: —",     font=("Segoe UI", 8))
        self._lbl_last.pack(side="left", padx=(0, 12))

        self._lbl_trend = tk.Label(self._sbar2, text="Trend: —",    font=("Segoe UI", 8))
        self._lbl_trend.pack(side="left", padx=(0, 12))

        self._lbl_ivr   = tk.Label(self._sbar2, text="IV Rank: —",  font=("Segoe UI", 8))
        self._lbl_ivr.pack(side="left", padx=(0, 12))

        self._lbl_cnt   = tk.Label(self._sbar2, text="0 ideas",     font=("Segoe UI", 8))
        self._lbl_cnt.pack(side="left", padx=(0, 12))

        self._progress  = ttk.Progressbar(self._sbar2, mode="indeterminate", length=100)
        self._progress.pack(side="left", padx=(0, 8))

        self._lbl_status = tk.Label(
            self._sbar2, textvariable=self._status_var,
            font=("Segoe UI", 8, "italic"),
        )
        self._lbl_status.pack(side="left")

    # --- row 3 : results table ---------------------------------------------
    def _build_table(self) -> None:
        self._tframe = tk.Frame(self)
        self._tframe.grid(row=3, column=0, sticky="nsew", padx=6, pady=2)
        self._tframe.columnconfigure(0, weight=1)
        self._tframe.rowconfigure(0, weight=1)

        col_ids = [c[0] for c in COLUMNS]
        self._tree = ttk.Treeview(
            self._tframe, columns=col_ids,
            show="headings", selectmode="browse",
        )

        vsb = ttk.Scrollbar(self._tframe, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(self._tframe, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        for col_id, header, width, anchor in COLUMNS:
            self._tree.heading(col_id, text=header,
                               command=lambda c=col_id: self._sort_by(c))
            self._tree.column(col_id, width=width, anchor=anchor,
                              minwidth=30, stretch=False)

        # Score colour tags
        for tag, fg_col in (
            ("score_excellent", _DARK["score_ex"]),
            ("score_good",      _DARK["score_gd"]),
            ("score_fair",      _DARK["score_fair"]),
            ("score_poor",      _DARK["score_poor"]),
        ):
            self._tree.tag_configure(tag, foreground=fg_col)
        self._tree.tag_configure("row_odd",  background=_DARK["row_odd"])
        self._tree.tag_configure("row_even", background=_DARK["row_even"])

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Button-3>",         self._on_rclick)

        # Context menu
        self._ctx = tk.Menu(self, tearoff=0)
        self._ctx.add_command(label="Send to IBKR",  command=self._on_send)
        self._ctx.add_command(label="Copy Row",       command=self._on_copy)
        self._ctx.add_command(label="Cancel Order",   command=self._on_cancel)
        self._ctx.add_separator()
        self._ctx.add_command(label="Refresh",        command=self._on_scan)
        self._ctx.add_command(label="View Legs",      command=self._view_legs_popup)

    # --- row 4 : detail panel ----------------------------------------------
    def _build_detail(self) -> None:
        self._det = tk.Frame(self, height=130)
        self._det.grid(row=4, column=0, sticky="ew", padx=6, pady=2)
        self._det.grid_propagate(False)
        for col in range(3):
            self._det.columnconfigure(col, weight=1)

        self._dcards: list[tk.LabelFrame] = []
        for col, title in enumerate(("Score Breakdown", "Net Greeks", "Legs")):
            card = tk.LabelFrame(
                self._det, text=title,
                font=("Segoe UI", 8, "bold"), padx=6, pady=4,
            )
            card.grid(row=0, column=col, sticky="nsew", padx=4, pady=2)
            self._dcards.append(card)

        self._lbl_score_detail = tk.Label(
            self._dcards[0], text="No idea selected",
            font=("Segoe UI", 8), justify="left",
        )
        self._lbl_score_detail.pack(anchor="w")

        self._lbl_greeks = tk.Label(
            self._dcards[1], text="—",
            font=("Segoe UI", 8), justify="left",
        )
        self._lbl_greeks.pack(anchor="w")

        self._lbl_legs = tk.Label(
            self._dcards[2], text="—",
            font=("Segoe UI", 8), justify="left", wraplength=320,
        )
        self._lbl_legs.pack(anchor="w")

    # --- row 5 : action bar ------------------------------------------------
    def _build_actions(self) -> None:
        self._abar = tk.Frame(self, padx=6, pady=4)
        self._abar.grid(row=5, column=0, sticky="ew")

        self._action_btns: dict[str, tk.Button] = {}
        specs = [
            ("scan",   "Scan Now",       "#2e4a7a", "#4f8ef7", self._on_scan),
            ("auto",   "Auto-Refresh",   "#1e4a2e", "#2ecc71", self._on_auto_toggle),
            ("copy",   "Copy",           "#2a2f3d", "#7b8299", self._on_copy),
            ("cancel", "Cancel Order",   "#4a1e1e", "#e74c3c", self._on_cancel),
            ("send",   "Send to IBKR",  "#1e3a4a", "#4f8ef7", self._on_send),
        ]
        for key, label, bg, fg, cmd in specs:
            b = tk.Button(
                self._abar, text=label, command=cmd,
                bg=bg, fg=fg,
                activebackground="#3a4460", activeforeground="#ffffff",
                font=("Segoe UI", 9, "bold"),
                relief="flat", padx=12, pady=5, cursor="hand2",
            )
            b.pack(side="left", padx=4)
            self._action_btns[key] = b

        _Tip(self._action_btns["scan"],   "Alt+R — scan for trade ideas")
        _Tip(self._action_btns["send"],   "Alt+S — send selected idea to IBKR")
        _Tip(self._action_btns["auto"],   "Toggle auto-refresh every N seconds")
        _Tip(self._action_btns["cancel"], "Cancel the selected IBKR order")
        _Tip(self._action_btns["copy"],   "Copy selected row to clipboard")

    # =======================================================================
    # THEME
    # =======================================================================

    def _pal(self) -> dict:
        return _DARK if self._dark_mode else _LIGHT

    def _apply_theme(self) -> None:
        c = self._pal()
        # Root is tk.Frame — supports bg safely
        self.configure(bg=c["bg"])
        for w in self.winfo_children():
            self._theme_widget(w, c)
        self._retag_table(c)

    def _theme_widget(self, w: tk.Widget, c: dict) -> None:
        try:
            if isinstance(w, ttk.Widget):
                pass  # ttk styling is controlled via ttk.Style — skip
            elif isinstance(w, tk.LabelFrame):
                w.configure(bg=c["card_bg"], fg=c["fg_muted"])
            elif isinstance(w, tk.Frame):
                w.configure(bg=c["panel_bg"])
            elif isinstance(w, tk.Label):
                w.configure(bg=c["panel_bg"], fg=c["fg"])
            elif isinstance(w, tk.Button):
                pass  # keep individual colour overrides
            elif isinstance(w, tk.Checkbutton):
                w.configure(
                    bg=c["panel_bg"], fg=c["fg"],
                    selectcolor=c["entry_bg"],
                    activebackground=c["panel_bg"],
                )
            elif isinstance(w, tk.Entry) and not isinstance(w, ttk.Widget):
                # CRITICAL: exclude ttk.Spinbox which subclasses tk.Entry
                w.configure(
                    bg=c["entry_bg"], fg=c["entry_fg"],
                    insertbackground=c["fg"], relief="flat",
                )
        except Exception:
            pass
        try:
            for child in w.winfo_children():
                self._theme_widget(child, c)
        except Exception:
            pass

    def _retag_table(self, c: dict) -> None:
        try:
            self._tree.tag_configure("score_excellent", foreground=c["score_ex"])
            self._tree.tag_configure("score_good",      foreground=c["score_gd"])
            self._tree.tag_configure("score_fair",      foreground=c["score_fair"])
            self._tree.tag_configure("score_poor",      foreground=c["score_poor"])
            self._tree.tag_configure("row_odd",  background=c["row_odd"])
            self._tree.tag_configure("row_even", background=c["row_even"])
        except Exception:
            pass

    def refresh_theme(self, dark: Optional[bool] = None) -> None:
        if dark is not None:
            self._dark_mode = dark
        self._apply_theme()

    # =======================================================================
    # EVENT BUS
    # =======================================================================

    def _reg_events(self) -> None:
        if not self._bus:
            return
        try:
            from .events_bridge import (
                EV_SYMBOL_SELECTED, EV_THEME_CHANGED, EV_IBKR_STATUS,
            )
            self._bus.subscribe(EV_SYMBOL_SELECTED, self._on_ext_sym)
            self._bus.subscribe(
                EV_THEME_CHANGED,
                lambda d: self.refresh_theme((d or {}).get("dark")),
            )
            self._bus.subscribe(
                EV_IBKR_STATUS,
                lambda d: self._on_ibkr_status(
                    (d or {}).get("idea_id"), (d or {}).get("status")
                ),
            )
        except Exception as exc:
            self._log.warning("Event registration failed: %s", exc)

    def _on_ext_sym(self, payload) -> None:
        sym = (payload or {}).get("symbol", "")
        if sym:
            self._sym_var.set(sym.upper())

    def _pub(self, event: str, payload=None) -> None:
        if not self._bus:
            return
        try:
            self._bus.publish(event, payload or {})
        except Exception as exc:
            self._log.warning("publish(%s): %s", event, exc)

    # =======================================================================
    # HOTKEYS
    # =======================================================================

    def _reg_hotkeys(self) -> None:
        if self._hkmgr:
            self._reg_via_adapter()
        else:
            self._reg_tkinter_fallback()

    def _reg_via_adapter(self) -> None:
        try:
            from .hotkey_adapter import HotkeyAdapter
            hk = (self._hkmgr
                  if isinstance(self._hkmgr, HotkeyAdapter)
                  else HotkeyAdapter(self._hkmgr))
            hk.register("alt+r", self._on_scan, "Trade Ideas: Scan")
            hk.register("alt+s", self._on_send, "Trade Ideas: Send to IBKR")
            hk.register("f5",    self._on_scan, "Trade Ideas: Refresh")
        except Exception as exc:
            self._log.warning("HotkeyAdapter: %s — using Tk bindings", exc)
            self._reg_tkinter_fallback()

    def _reg_tkinter_fallback(self) -> None:
        root = self.winfo_toplevel()
        root.bind("<Alt-r>", lambda _: self._on_scan(), add="+")
        root.bind("<Alt-s>", lambda _: self._on_send(), add="+")
        root.bind("<F5>",    lambda _: self._on_scan(), add="+")

    # =======================================================================
    # SCAN — main strategy engine
    # =======================================================================

    def _on_scan(self, _=None) -> None:
        if self._loading:
            return
        self._set_loading(True, "Scanning...")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        import random

        sym  = self._sym_var.get().strip().upper() or "SPY"
        dte  = self._dte_var.get()
        qty  = self._qty_var.get()
        mode = self._mode_var.get()

        # Fetch market data
        data = None
        try:
            if self._api:
                data = self._api.get(f"/market/snapshot/{sym}")
        except Exception as exc:
            self._log.warning("API fetch: %s", exc)

        # Fallback mock data
        if not data:
            px   = _PRICES.get(sym, 100.0) + random.uniform(-3, 3)
            iv30 = round(random.uniform(0.15, 0.45), 3)
            hv20 = round(iv30 * random.uniform(0.7, 1.2), 3)
            data = {
                "symbol": sym,
                "price":  round(px, 2),
                "iv30":   iv30,
                "hv20":   hv20,
                "iv_rank": round(random.uniform(20, 85), 1),
                "iv_pct":  round(random.uniform(25, 80), 1),
                "price_history": [
                    px * (1 + random.uniform(-0.005, 0.005))
                    for _ in range(20)
                ],
            }

        market = {
            "underlying_price": data["price"],
            "iv30":             data["iv30"],
            "hv20":             data["hv20"],
            "iv_rank":          data["iv_rank"],
            "iv_pct":           data.get("iv_pct", 50.0),
            "price_history":    data.get("price_history", []),
        }

        strat_map = {
            "Credit":   StrategyType.CREDIT_SPREAD,
            "Debit":    StrategyType.DEBIT_SPREAD,
            "Condor":   StrategyType.IRON_CONDOR,
            "Calendar": StrategyType.CALENDAR,
        }

        ideas: List[TradeIdea] = []
        try:
            if mode == "Auto":
                ideas = self._engine.generate_ideas(sym, dte, qty, market)
            else:
                ideas = self._engine.generate_ideas(
                    sym, dte, qty, market,
                    strategy=strat_map.get(mode),
                )
        except Exception as exc:
            self._log.exception("StrategyEngine error: %s", exc)

        self.after(0, self._update, ideas, market)

    def _update(self, ideas: List[TradeIdea], market: dict) -> None:
        self._ideas = ideas
        self._cnt   = len(ideas)

        now = datetime.datetime.now().strftime("%H:%M:%S")
        self._lbl_last.configure(text=f"Last: {now}")

        trend = market.get("trend", "—")
        if hasattr(trend, "value"):
            trend = trend.value
        self._lbl_trend.configure(text=f"Trend: {trend}")
        self._lbl_ivr.configure(text=f"IV Rank: {market.get('iv_rank', 0.0):.1f}")
        self._lbl_cnt.configure(
            text=f"{self._cnt} idea{'s' if self._cnt != 1 else ''}"
        )

        self._render()
        self._set_loading(False, "Done")
        try:
            from .events_bridge import EV_IDEAS_UPDATED
            self._pub(EV_IDEAS_UPDATED, {
                "count": self._cnt,
                "symbol": self._sym_var.get(),
            })
        except Exception:
            pass

    # =======================================================================
    # SELL PREMIUM SCAN
    # =======================================================================

    def _on_sell_premium_scan(self) -> None:
        if not _HAS_SP:
            messagebox.showinfo(
                "Sell Premium",
                "sell_premium_scanner.py not found in trade_ideas/.\n"
                "Please add the module and restart.",
            )
            return
        if self._loading:
            return
        self._set_loading(True, "Running sell-premium scan...")
        threading.Thread(target=self._sp_worker, daemon=True).start()

    def _sp_worker(self) -> None:
        import random

        sym      = self._sym_var.get().strip().upper() or "SPY"
        qty      = self._qty_var.get()
        dte_mode = self._dte_mode_var.get()

        mode_map = {"0 DTE": DTEMode.DTE_0, "7 DTE": DTEMode.DTE_7, "Both": DTEMode.BOTH}
        dm = mode_map.get(dte_mode, DTEMode.BOTH)

        data = None
        try:
            if self._api:
                data = self._api.get(f"/market/snapshot/{sym}")
        except Exception as exc:
            self._log.warning("Sell-premium API fetch: %s", exc)

        if not data:
            px   = _PRICES.get(sym, 100.0) + random.uniform(-3, 3)
            iv30 = round(random.uniform(0.15, 0.45), 3)
            hv20 = round(iv30 * random.uniform(0.7, 1.2), 3)
            data = {
                "symbol": sym,
                "price":  round(px, 2),
                "iv30":   iv30,
                "hv20":   hv20,
                "iv_rank": round(random.uniform(20, 85), 1),
                "iv_pct":  round(random.uniform(25, 80), 1),
                "price_history": [
                    px * (1 + random.uniform(-0.005, 0.005))
                    for _ in range(20)
                ],
            }

        market = {
            "price":         data["price"],
            "iv30":          data["iv30"],
            "hv20":          data["hv20"],
            "iv_rank":       data["iv_rank"],
            "iv_pct":        data.get("iv_pct", 50.0),
            "price_history": data.get("price_history", []),
        }

        ideas: List[TradeIdea] = []
        try:
            scanner = SellPremiumScanner(api_client=self._api)
            ideas   = scanner.scan(sym, dm, market, contracts=qty)
        except Exception as exc:
            self._log.exception("SellPremiumScanner error: %s", exc)

        self.after(0, self._finish_sell_premium, ideas, market)

    def _finish_sell_premium(
        self, ideas: List[TradeIdea], market: dict
    ) -> None:
        self._ideas = ideas
        self._cnt   = len(ideas)

        now      = datetime.datetime.now().strftime("%H:%M:%S")
        dte_mode = self._dte_mode_var.get()

        self._lbl_last.configure(text=f"Sell Premium: {now}")
        self._lbl_cnt.configure(
            text=f"{self._cnt} idea{'s' if self._cnt != 1 else ''}"
        )
        self._lbl_ivr.configure(
            text=f"IV Rank: {market.get('iv_rank', 0.0):.1f}"
        )
        self._status_var.set(f"Sell Premium ({dte_mode}) — {self._cnt} results")

        # _populate_table is the canonical name used by sell-premium code;
        # _render delegates to it so both names always work.
        self._populate_table()
        self._set_loading(False, "Sell-premium scan complete")

    # =======================================================================
    # TABLE RENDER & SORT
    # =======================================================================

    def _render(self) -> None:
        self._populate_table()

    def _populate_table(self) -> None:
        self._sort_ideas()
        # Clear existing rows
        for row in self._tree.get_children():
            self._tree.delete(row)

        for idx, idea in enumerate(self._ideas):
            values = tuple(COL_FN[c[0]](idea) for c in COLUMNS)
            row_tag = "row_odd" if idx % 2 else "row_even"
            score_tag = idea.score.color_tag  # score_excellent/good/fair/poor
            self._tree.insert("", "end", iid=idea.id,
                              values=values, tags=(row_tag, score_tag))

    def _sort_by(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col  = col
            self._sort_desc = True
        self._populate_table()

    def _sort_ideas(self) -> None:
        col = self._sort_col

        def key_fn(idea: TradeIdea):
            raw = COL_FN.get(col, lambda i: "")(idea)
            # Try numeric sort
            try:
                return float(str(raw).replace("$", "").replace("%", "").replace("+", ""))
            except (ValueError, TypeError):
                return str(raw).lower()

        self._ideas.sort(key=key_fn, reverse=self._sort_desc)

    # =======================================================================
    # SELECTION & DETAIL
    # =======================================================================

    def _on_select(self, _=None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        idea = next((i for i in self._ideas if i.id == iid), None)
        if idea is None:
            return
        self._sel = idea
        self._fill_detail(idea)
        try:
            from .events_bridge import EV_IDEA_SELECTED
            self._pub(EV_IDEA_SELECTED, {"idea_id": idea.id, "symbol": idea.symbol})
        except Exception:
            pass

    def _fill_detail(self, idea: TradeIdea) -> None:
        # Score breakdown
        sc = idea.score
        score_txt = (
            f"Composite : {sc.composite:.1f}  ({sc.grade})\n"
            f"POP Score : {sc.pop_score:.1f}\n"
            f"IV Rank   : {sc.iv_rank_score:.1f}\n"
            f"Trend     : {sc.trend_score:.1f}\n"
            f"Reward/Rk : {sc.reward_risk:.1f}\n"
            f"Liquidity : {sc.liquidity_score:.1f}"
        )
        self._lbl_score_detail.configure(text=score_txt)

        # Greeks
        g = idea.net_greeks
        greeks_txt = (
            f"Delta : {g.delta:+.4f}\n"
            f"Gamma : {g.gamma:+.4f}\n"
            f"Theta : {g.theta:+.4f}\n"
            f"Vega  : {g.vega:+.4f}\n"
            f"IV    : {g.iv:.1%}"
        )
        self._lbl_greeks.configure(text=greeks_txt)

        # Legs
        if idea.legs:
            lines = []
            for leg in idea.legs:
                lines.append(
                    f"{leg.action:4s} {leg.qty}x {leg.symbol} "
                    f"{leg.expiry} {leg.strike:.0f}{leg.right} "
                    f"@ ${leg.mid_price:.2f}"
                )
            self._lbl_legs.configure(text="\n".join(lines))
        else:
            self._lbl_legs.configure(text="No legs available")

    def _on_rclick(self, event) -> None:
        row = self._tree.identify_row(event.y)
        if row:
            self._tree.selection_set(row)
            self._on_select()
        try:
            self._ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx.grab_release()

    def _view_legs_popup(self) -> None:
        if not self._sel:
            messagebox.showinfo("Legs", "No idea selected.")
            return
        idea = self._sel
        c    = self._pal()

        win = tk.Toplevel(self)
        win.title(f"Legs — {idea.symbol} {idea.strategy.value}")
        win.configure(bg=c["bg"])
        win.geometry("520x340")
        win.resizable(True, True)

        title = tk.Label(
            win,
            text=f"{idea.symbol}  |  {idea.strategy.value}  |  DTE {idea.dte}  |  "
                 f"Score {idea.score.composite:.1f} ({idea.score.grade})",
            font=("Segoe UI", 10, "bold"),
            bg=c["bg"], fg=c["fg"],
        )
        title.pack(pady=(10, 4), padx=10, anchor="w")

        fr = tk.Frame(win, bg=c["card_bg"], relief="flat")
        fr.pack(fill="both", expand=True, padx=10, pady=6)

        headers = ["Action", "Qty", "Symbol", "Expiry", "Strike", "Right", "Mid Price"]
        for col, h in enumerate(headers):
            tk.Label(
                fr, text=h, font=("Segoe UI", 8, "bold"),
                bg=c["card_bg"], fg=c["fg_muted"],
            ).grid(row=0, column=col, padx=8, pady=4, sticky="w")

        if idea.legs:
            for row_idx, leg in enumerate(idea.legs, start=1):
                for col, val in enumerate([
                    leg.action, str(leg.qty), leg.symbol, leg.expiry,
                    f"{leg.strike:.2f}", leg.right, f"${leg.mid_price:.2f}",
                ]):
                    tk.Label(
                        fr, text=val, font=("Segoe UI", 9),
                        bg=c["card_bg"], fg=c["fg"],
                    ).grid(row=row_idx, column=col, padx=8, pady=2, sticky="w")
        else:
            tk.Label(
                fr, text="No legs available",
                font=("Segoe UI", 9), bg=c["card_bg"], fg=c["fg_muted"],
            ).grid(row=1, column=0, columnspan=7, padx=8, pady=6)

        tk.Button(
            win, text="Close", command=win.destroy,
            bg=c["btn_bg"], fg=c["btn_fg"], relief="flat",
            font=("Segoe UI", 9), padx=10, pady=4, cursor="hand2",
        ).pack(pady=8)

    # =======================================================================
    # ACTIONS
    # =======================================================================

    def _on_send(self, _=None) -> None:
        if not self._sel:
            messagebox.showinfo("Send to IBKR", "Please select a trade idea first.")
            return
        idea    = self._sel
        dry_run = self._dry_var.get()
        acct    = self._acct_var.get().strip()

        msg = (
            f"Send to IBKR {'(DRY RUN)' if dry_run else ''}\n\n"
            f"  Symbol   : {idea.symbol}\n"
            f"  Strategy : {idea.strategy.value}\n"
            f"  DTE      : {idea.dte}\n"
            f"  Legs     : {len(idea.legs)}\n"
            f"  Net      : ${idea.net_credit:+.2f}\n"
            f"  Score    : {idea.score.composite:.1f} ({idea.score.grade})\n"
            f"  Account  : {acct or 'default'}\n\n"
            "Confirm?"
        )
        if not messagebox.askyesno("Confirm Order", msg):
            return

        self._bridge._dry_run = dry_run
        self._bridge._account = acct
        ok = self._bridge.submit(idea)
        if ok:
            self._log.info("Submitted %s to IBKR (dry=%s)", idea.id, dry_run)
            self._render()
            try:
                from .events_bridge import EV_IBKR_SENT
                self._pub(EV_IBKR_SENT, {"idea_id": idea.id, "symbol": idea.symbol})
            except Exception:
                pass
        else:
            messagebox.showerror("IBKR Error", "Order submission failed. Check logs.")

    def _on_cancel(self, _=None) -> None:
        if not self._sel:
            messagebox.showinfo("Cancel", "No idea selected.")
            return
        idea = self._sel
        if idea.ibkr_order_id is None:
            messagebox.showinfo("Cancel", "No IBKR order associated with this idea.")
            return
        if messagebox.askyesno("Cancel Order",
                               f"Cancel order #{idea.ibkr_order_id} for {idea.symbol}?"):
            self._bridge.cancel(idea)
            self._render()

    def _on_copy(self, _=None) -> None:
        if not self._sel:
            return
        idea = self._sel
        row  = "\t".join(COL_FN[c[0]](idea) for c in COLUMNS)
        self.clipboard_clear()
        self.clipboard_append(row)
        self._status_var.set("Row copied to clipboard")
        self.after(2000, lambda: self._status_var.set("Ready"))

    def _on_ibkr_status(self, idea_id: Optional[str], status) -> None:
        if not idea_id:
            return
        idea = next((i for i in self._ideas if i.id == idea_id), None)
        if not idea:
            return
        if isinstance(status, IdeaStatus):
            idea.status = status
        elif isinstance(status, str):
            try:
                idea.status = IdeaStatus(status)
            except ValueError:
                self._log.warning("Unknown IBKR status: %s", status)
                return
        self.after(0, self._render)

    # =======================================================================
    # AUTO-REFRESH
    # =======================================================================

    def _on_auto_toggle(self) -> None:
        self._auto_var.set(not self._auto_var.get())
        btn = self._action_btns.get("auto")
        if self._auto_var.get():
            if btn:
                btn.configure(bg="#1e6a3e", text="Auto ON")
            self._schedule()
        else:
            if btn:
                btn.configure(bg="#1e4a2e", text="Auto-Refresh")
            self._cancel_sched()

    def _schedule(self) -> None:
        self._cancel_sched()
        if self._refresh_interval > 0 and self._auto_var.get():
            self._rjob = self.after(self._refresh_interval * 1000, self._tick)

    def _cancel_sched(self) -> None:
        if self._rjob:
            try:
                self.after_cancel(self._rjob)
            except Exception:
                pass
            self._rjob = None

    def _tick(self) -> None:
        if self._auto_var.get():
            self._on_scan()
            self._schedule()

    # =======================================================================
    # CONTROLS HELPERS
    # =======================================================================

    def _on_mode_change(self, _=None) -> None:
        mode = self._mode_var.get()
        for key, btn in self._strat_btns.items():
            if key == "SellPremium":
                continue
            active = (
                (key == "Auto"     and mode == "Auto")     or
                (key == "Credit"   and mode == "Credit")   or
                (key == "Debit"    and mode == "Debit")    or
                (key == "Condor"   and mode == "Condor")   or
                (key == "Calendar" and mode == "Calendar")
            )
            try:
                btn.configure(relief="sunken" if active else "flat")
            except Exception:
                pass

    def _quick(self, mode: str) -> None:
        self._mode_var.set(mode)
        self._on_mode_change()
        self._on_scan()

    def _on_dry_toggle(self) -> None:
        dry = self._dry_var.get()
        self._bridge._dry_run = dry
        self._log.info("Dry run: %s", dry)
        self._status_var.set(f"Dry Run {'ON' if dry else 'OFF'}")
        self.after(2000, lambda: self._status_var.set("Ready"))

    def _set_loading(self, state: bool, msg: str = "") -> None:
        self._loading = state
        self._status_var.set(msg)
        if state:
            self._progress.start(12)
        else:
            self._progress.stop()
        scan_btn = self._action_btns.get("scan")
        if scan_btn:
            scan_btn.configure(state="disabled" if state else "normal")
