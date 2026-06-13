import tkinter as tk
from .layout import build_layout
from .events import bind_events
from .api_client import send_request
from .theme import theme_manager
from .settings_manager import settings
from .logger import logger
from .hotkeys import HotkeyManager

def main():
    root = tk.Tk()
    root.title("FastAPI Control Center")

    # Load window size from settings
    root.geometry(f"{settings.get('window_width')}x{settings.get('window_height')}")

    # Build layout
    tabs, console = build_layout(root)

    # Attach console to logger
    logger.attach_console(console)

    # Apply theme
    theme_manager.current = settings.get("theme")
    theme_manager.apply(root)

    # API wrapper
    def api(method, endpoint, payload=None):
        logger.log(f"API {method} {endpoint}")
        return send_request(method, endpoint, payload)

    # Bind events (tabs + auto-refresh)
    refresh_all = bind_events(tabs, api, console)

    # Hotkeys
    hotkeys = HotkeyManager(root)
    hotkeys.setup_defaults(
        refresh_all=refresh_all,
        send_request=lambda: tabs["Trading Panel"].event_generate("<<SendRequest>>"),
        clear_console=lambda: console.delete("1.0", "end"),
        open_trading=lambda: root.event_generate("<<OpenTrading>>")
    )

    # Save window size on close
    def on_close():
        w = root.winfo_width()
        h = root.winfo_height()
        settings.set("window_width", w)
        settings.set("window_height", h)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
