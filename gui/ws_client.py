import threading
import websocket
import json

class WebSocketClient:
    def __init__(self, url, on_message):
        self.url = url
        self.on_message = on_message
        self.ws = None
        self.thread = None

    def start(self):
        def run():
            self.ws = websocket.WebSocketApp(
                self.url,
                on_message=lambda ws, msg: self.on_message(json.loads(msg))
            )
            self.ws.run_forever()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        if self.ws:
            self.ws.close()

