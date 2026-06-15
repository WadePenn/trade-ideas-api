import tkinter as tk
from tkinter import ttk

def build_layout(root):
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    tabs = {}
    for name in ["Overview", "Positions", "Orders", "Market Data", "Trading Panel", "Settings"]:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=name)
        tabs[name] = frame
def build_layout(root):
    import tkinter as tk
    from tkinter import ttk

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    # Existing tabs...
    # tabs["Trading Panel"], tabs["Console"], etc.

    # -----------------------------
    # NEW: Trade Ideas Tab
    # -----------------------------
    trade_frame = tk.Frame(notebook)
    notebook.add(trade_frame, text="Trade Ideas")

    # Inputs
    tk.Label(trade_frame, text="Symbol:").grid(row=0, column=0, sticky="w")
    symbol_entry = tk.Entry(trade_frame, width=10)
    symbol_entry.grid(row=0, column=1, sticky="w")

    tk.Label(trade_frame, text="DTE:").grid(row=1, column=0, sticky="w")
    dte_entry = tk.Entry(trade_frame, width=10)
    dte_entry.grid(row=1, column=1, sticky="w")

    tk.Label(trade_frame, text="Contracts:").grid(row=2, column=0, sticky="w")
    contracts_entry = tk.Entry(trade_frame, width=10)
    contracts_entry.grid(row=2, column=1, sticky="w")

    # Trade type buttons
    btn_frame = tk.Frame(trade_frame)
    btn_frame.grid(row=3, column=0, columnspan=2, pady=10)

    trade_buttons = {
        "credit": tk.Button(btn_frame, text="Credit Spread"),
        "debit": tk.Button(btn_frame, text="Debit Spread"),
        "condor": tk.Button(btn_frame, text="Iron Condor"),
        "calendar": tk.Button(btn_frame, text="Calendar"),
    }

    for i, b in enumerate(trade_buttons.values()):
        b.grid(row=0, column=i, padx=5)

    # Results table
    results = tk.Text(trade_frame, height=20, width=80)
    results.grid(row=4, column=0, columnspan=4, pady=10)

    return {
        "root": root,
        "Trade Ideas": {
            "frame": trade_frame,
            "symbol": symbol_entry,
            "dte": dte_entry,
            "contracts": contracts_entry,
            "buttons": trade_buttons,
            "results": results,
        }
    }

    # Global console
    console_frame = ttk.Frame(root)
    console_frame.pack(fill="x")

    console_label = ttk.Label(console_frame, text="Global Console")
    console_label.pack()

    console = tk.Text(console_frame, height=8)
    console.pack(fill="x")

    return tabs, console
from trade_ideas.layout_integration import register_trade_ideas_tab
from trade_ideas.api_adapter import TradeIdeasAPIAdapter
from trade_ideas.events_bridge import wrap_event_bus
from trade_ideas.hotkey_adapter import HotkeyAdapter

ti_panel = register_trade_ideas_tab(
    notebook      = your_notebook,
    api_client    = TradeIdeasAPIAdapter(your_api_client),
    event_bus     = wrap_event_bus(your_event_bus),
    theme_manager = your_theme_mgr,
    hotkey_mgr    = HotkeyAdapter(your_hotkey_mgr),
    app_logger    = your_logger,
    dry_run       = False,         # live IBKR
    refresh_interval = 60,
)

