import tkinter as tk
from tkinter import ttk

def init_overview_tab(frame):
    label = ttk.Label(frame, text="System Overview")
    label.pack(pady=10)

    info = ttk.Label(frame, text="FastAPI Control Center — All Systems Online")
    info.pack(pady=5)

    return lambda: None
