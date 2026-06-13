import os
import datetime

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "control_center.log")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

class Logger:
    def __init__(self, console_widget=None):
        self.console = console_widget

    def attach_console(self, widget):
        self.console = widget

    def log(self, msg):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {msg}\n"

        # Write to file
        with open(LOG_FILE, "a") as f:
            f.write(line)

        # Write to GUI console
        if self.console:
            self.console.insert("end", line)
            self.console.see("end")

logger = Logger()
