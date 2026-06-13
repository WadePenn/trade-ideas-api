import sys
import traceback
import tkinter as tk
from tkinter import messagebox

try:
    from trade_ideas.panel import TradeIdeasPanel

    root = tk.Tk()
    root.title("Trade Ideas")
    root.geometry("1400x820")
    root.resizable(True, True)
    root.lift()
    root.attributes("-topmost", True)
    root.after(500, lambda: root.attributes("-topmost", False))

    panel = TradeIdeasPanel(root)
    panel.pack(fill="both", expand=True)
    root.mainloop()

except Exception:
    err = traceback.format_exc()
    root2 = tk.Tk()
    root2.withdraw()
    messagebox.showerror("Trade Ideas Launch Error", err)
    sys.exit(1)
