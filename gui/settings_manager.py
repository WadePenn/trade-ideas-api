import json
import os

SETTINGS_FILE = "gui_settings.json"

DEFAULT_SETTINGS = {
    "theme": "dark",
    "window_width": 1200,
    "window_height": 800,
    "refresh_positions": 5,
    "refresh_orders": 10,
    "refresh_market": 3,
    "last_endpoint": "/health",
    "saved_payload": "{}"
}

class SettingsManager:
    def __init__(self):
        self.settings = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    self.settings.update(json.load(f))
            except:
                pass

    def save(self):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.settings, f, indent=4)

    def get(self, key):
        return self.settings.get(key, DEFAULT_SETTINGS[key])

    def set(self, key, value):
        self.settings[key] = value
        self.save()

settings = SettingsManager()
