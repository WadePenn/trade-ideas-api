import tkinter as tk
from tkinter import ttk
from ..utils.json_tools import pretty_json
from ..logger import logger
from .popout_button import add_popout_button

def init_orders_tab(frame, api, console):
    header = ttk.Label(frame, text="Orders")
    header.pack(pady=5)

    text = tk.Text(frame, height=20)
    text.pack(fill="both", expand=True)

    add_popout_button(frame, "Orders", lambda parent: ttk.Frame(parent))

    def refresh():
        text.delete("1.0", "end")
        data = api("GET", "/orders")
        text.insert("end", pretty_json(data))
        logger.log("Orders refreshed")

    return refresh
