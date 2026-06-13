import tkinter as tk
from tkinter import ttk
from ..multiwindow import window_manager

def add_popout_button(frame, title, widget_factory):
    btn = ttk.Button(frame, text="Pop Out Window", command=lambda: window_manager.popout(title, widget_factory))
    btn.pack(pady=5)
