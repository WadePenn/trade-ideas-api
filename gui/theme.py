import tkinter as tk
from tkinter import ttk

class ThemeManager:
    def __init__(self):
        self.current = "dark"
        self.themes = {
            "dark": {
                "bg": "#1e1e1e",
                "fg": "#ffffff",
                "accent": "#3a8cff",
                "text_bg": "#252526",
                "text_fg": "#d4d4d4",
                "button_bg": "#333333",
                "button_fg": "#ffffff"
            },
            "light": {
                "bg": "#f0f0f0",
                "fg": "#000000",
                "accent": "#0066cc",
                "text_bg": "#ffffff",
                "text_fg": "#000000",
                "button_bg": "#e0e0e0",
                "button_fg": "#000000"
            }
        }

    def apply(self, root):
        theme = self.themes[self.current]

        root.configure(bg=theme["bg"])

        style = ttk.Style()
        style.theme_use("default")

        style.configure("TFrame", background=theme["bg"])
        style.configure("TLabel", background=theme["bg"], foreground=theme["fg"])
        style.configure("TButton", background=theme["button_bg"], foreground=theme["button_fg"])
        style.configure("TNotebook", background=theme["bg"])
        style.configure("TNotebook.Tab", background=theme["button_bg"], foreground=theme["fg"])

        # Apply to all children recursively
        self._apply_recursive(root, theme)

    def _apply_recursive(self, widget, theme):
        for child in widget.winfo_children():
            try:
                child.configure(bg=theme["bg"], fg=theme["fg"])
            except:
                pass

            if isinstance(child, tk.Text):
                child.configure(
                    bg=theme["text_bg"],
                    fg=theme["text_fg"],
                    insertbackground=theme["text_fg"]
                )

            self._apply_recursive(child, theme)

theme_manager = ThemeManager()
