import tkinter as tk
from tkinter import ttk
from ..utils.json_tools import pretty_json
from ..settings_manager import settings
from ..logger import logger
from .popout_button import add_popout_button

def init_trading_tab(frame, api, console):
    header = ttk.Label(frame, text="Trading Panel")
    header.pack(pady=5)

    method_var = tk.StringVar(value="GET")
    endpoint_var = tk.StringVar(value=settings.get("last_endpoint"))

    payload_box = tk.Text(frame, height=10)
    payload_box.insert("end", settings.get("saved_payload"))
    payload_box.pack(fill="x", pady=5)

    result_box = tk.Text(frame, height=10)
    result_box.pack(fill="both", expand=True)

    method_menu = ttk.OptionMenu(frame, method_var, "GET", "GET", "POST", "PUT", "DELETE")
    method_menu.pack(pady=5)

    endpoint_entry = ttk.Entry(frame, textvariable=endpoint_var)
    endpoint_entry.pack(fill="x", pady=5)

    def send():
        method = method_var.get()
        endpoint = endpoint_var.get()
        settings.set("last_endpoint", endpoint)

        try:
            payload = payload_box.get("1.0", "end").strip()
            settings.set("saved_payload", payload)
            payload = eval(payload) if payload else None
        except:
            payload = None

        result = api(method, endpoint, payload)
        result_box.delete("1.0", "end")
        result_box.insert("end", pretty_json(result))

        logger.log(f"Sent {method} {endpoint}")

    frame.bind("<<SendRequest>>", lambda e: send())

    btn = ttk.Button(frame, text="Send Request", command=send)
    btn.pack(pady=10)

    add_popout_button(frame, "Trading Panel", lambda parent: ttk.Frame(parent))

    return send
