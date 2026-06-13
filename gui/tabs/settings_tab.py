import tkinter as tk
from tkinter import ttk
from ..settings_manager import settings
from ..theme import theme_manager
from ..logger import logger
from .popout_button import add_popout_button

def init_settings_tab(frame):
    header = ttk.Label(frame, text="Settings")
    header.pack(pady=5)

    add_popout_button(frame, "Settings", lambda parent: ttk.Frame(parent))

    theme_label = ttk.Label(frame, text="Theme:")
    theme_label.pack()

    theme_var = tk.StringVar(value=settings.get("theme"))

    def apply_theme():
        settings.set("theme", theme_var.get())
        theme_manager.current = theme_var.get()
        theme_manager.apply(frame.winfo_toplevel())
        logger.log(f"Theme changed to {theme_var.get()}")

    ttk.Radiobutton(frame, text="Dark", variable=theme_var, value="dark", command=apply_theme).pack()
    ttk.Radiobutton(frame, text="Light", variable=theme_var, value="light", command=apply_theme).pack()

    def add_interval(label, key):
        ttk.Label(frame, text=label).pack()
        var = tk.StringVar(value=str(settings.get(key)))

        entry = ttk.Entry(frame, textvariable=var)
        entry.pack()

        def save():
            try:
                val = int(var.get())
                settings.set(key, val)
                logger.log(f"Updated {key} to {val}")
            except:
                pass

        ttk.Button(frame, text="Save", command=save).pack(pady=2)

    add_interval("Positions Refresh (sec)", "refresh_positions")
    add_interval("Orders Refresh (sec)", "refresh_orders")
    add_interval("Market Refresh (sec)", "refresh_market")

    return lambda: None
