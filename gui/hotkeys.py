class HotkeyManager:
    def __init__(self, root):
        self.root = root
        self.bindings = {}

    def bind(self, combo, func):
        self.bindings[combo] = func
        self.root.bind(combo, lambda e: func())

    def setup_defaults(self, refresh_all, send_request, clear_console, open_trading):
        self.bind("<F5>", lambda e: refresh_all())
        self.bind("<Control-Return>", lambda e: send_request())
        self.bind("<Control-l>", lambda e: clear_console())
        self.bind("<Control-t>", lambda e: open_trading())
