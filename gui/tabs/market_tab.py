import tkinter as tk
from tkinter import ttk
from ..utils.json_tools import pretty_json
from ..chart_engine import chart_engine
from ..ws_client import WebSocketClient
from ..logger import logger
from .popout_button import add_popout_button

def init_market_tab(frame, api, console):
    header = ttk.Label(frame, text="Market Data")
    header.pack(pady=5)

    text = tk.Text(frame, height=15)
    text.pack(fill="both", expand=True)

    chart_frame = ttk.Frame(frame)
    chart_frame.pack(fill="x", pady=10)

    price_history = []

    def on_ws_message(msg):
        text.delete("1.0", "end")
        text.insert("end", pretty_json(msg))

        if "price" in msg:
            price_history.append(msg["price"])
            if len(price_history) > 100:
                price_history.pop(0)

        for w in chart_frame.winfo_children():
            w.destroy()

        if price_history:
            chart_engine.render_line(chart_frame, price_history)

    ws = WebSocketClient("ws://127.0.0.1:8000/ws/market", on_ws_message)
    ws.start()

    add_popout_button(frame, "Market Data", lambda parent: ttk.Frame(parent))

    def refresh():
        data = api("GET", "/market")
        text.delete("1.0", "end")
        text.insert("end", pretty_json(data))
        logger.log("Market data refreshed")

    return refresh
