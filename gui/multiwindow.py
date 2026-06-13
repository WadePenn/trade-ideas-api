import tkinter as tk

class WindowManager:
    def __init__(self):
        self.windows = []

    def popout(self, title, widget_factory):
        win = tk.Toplevel()
        win.title(title)
        frame = widget_factory(win)
        frame.pack(fill="both", expand=True)
        self.windows.append(win)

window_manager = WindowManager()
