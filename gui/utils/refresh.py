import threading
import time

class AutoRefresher:
    def __init__(self):
        self.tasks = []
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def add(self, interval, func):
        self.tasks.append((interval, time.time(), func))

    def _loop(self):
        while self.running:
            now = time.time()
            for i, (interval, last, func) in enumerate(self.tasks):
                if now - last >= interval:
                    threading.Thread(target=func, daemon=True).start()
                    self.tasks[i] = (interval, now, func)
            time.sleep(0.2)
