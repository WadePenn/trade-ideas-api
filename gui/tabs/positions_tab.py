import tkinter as tk
from tkinter import ttk
from ..utils.json_tools import pretty_json
from ..chart_engine import chart_engine
from ..logger import logger
from .popout_button import add_popout_button

def init_positions_tab(frame, api, console):
    header = ttk.Label(frame, text="Positions")
    header.pack(pady=5)

    text = tk.Text(frame, height=20)
    text.pack(fill="both", expand=True)

    chart_frame = ttk.Frame(frame)
    chart_frame.pack(fill="x", pady=10)

    # Pop-out support
    def widget_factory(parent):
        f = ttk.Frame(parent)
        t = tk.Text(f, height=20)
        t.pack(fill="both", expand=True)
        return f

    add_popout_button(frame, "Positions", widget_factory)

    def refresh():
        text.delete("1.0", "end")
        data = api("GET", "/positions")
        text.insert("end", pretty_json(data))

        chart_data = []
        if isinstance(data, dict) and "positions" in data:
            for pos in data["positions"]:
                if "unrealizedPnL" in pos:
                    chart_data.append(pos["unrealizedPnL"])

        for w in chart_frame.winfo_children():
            w.destroy()

        if chart_data:
            chart_engine.render_line(chart_frame, chart_data)

        logger.log("Positions refreshed")

    return refresh
