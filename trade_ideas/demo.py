# demo.py — Standalone launcher for TradeIdeasPanel.
#
# Tries RealAPIClient (live FastAPI server) first.
# Falls back to MockAPIClient automatically if the server is not running.
#
# Run:
#   py -3.11 run_demo.py

from __future__ import annotations

import logging
import sys
import tkinter as tk

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("trade_ideas.demo")

from .panel import TradeIdeasPanel
from .mock_client import MockAPIClient


# ---------------------------------------------------------------------------
# RealAPIClient — lightweight HTTP wrapper for the FastAPI backend.
# No external deps beyond the stdlib `urllib` — uses requests if available.
# ---------------------------------------------------------------------------
class RealAPIClient:
    """
    Calls the local FastAPI server at http://localhost:8000.
    Falls back gracefully to None on connection errors so the panel
    can revert to mock data automatically.
    """

    BASE = "http://localhost:8000"

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.BASE = base_url.rstrip("/")
        try:
            import requests
            self._requests = requests
            self._session  = requests.Session()
            self._session.headers.update({
                "Content-Type": "application/json",
                "Accept":       "application/json",
            })
            log.info("RealAPIClient ready → %s", self.BASE)
        except ImportError:
            self._requests = None
            self._session  = None
            log.warning("requests not installed — RealAPIClient disabled")

    # ------------------------------------------------------------------
    def is_alive(self) -> bool:
        if self._session is None:
            return False
        try:
            r = self._session.get(self.BASE + "/health", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    def get(self, path: str, timeout: float = 8.0, **kw):
        if self._session is None:
            return None
        url = self.BASE + path
        try:
            r = self._session.get(url, timeout=timeout, **kw)
            r.raise_for_status()
            return r.json()
        except self._requests.exceptions.ConnectionError:
            log.warning("GET %s — server not reachable", url)
        except self._requests.exceptions.Timeout:
            log.warning("GET %s — timed out", url)
        except self._requests.exceptions.HTTPError as exc:
            log.warning("GET %s — HTTP %s", url, exc.response.status_code)
        except Exception as exc:
            log.warning("GET %s — %s", url, exc)
        return None

    # ------------------------------------------------------------------
    def post(self, path: str, json=None, timeout: float = 10.0, **kw):
        if self._session is None:
            return None
        url = self.BASE + path
        try:
            r = self._session.post(url, json=json, timeout=timeout, **kw)
            r.raise_for_status()
            return r.json()
        except self._requests.exceptions.ConnectionError:
            log.warning("POST %s — server not reachable", url)
        except self._requests.exceptions.Timeout:
            log.warning("POST %s — timed out", url)
        except self._requests.exceptions.HTTPError as exc:
            log.warning("POST %s — HTTP %s", url, exc.response.status_code)
        except Exception as exc:
            log.warning("POST %s — %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# DemoApp
# ---------------------------------------------------------------------------
class DemoApp:
    TITLE  = "Trade Ideas Panel"
    WIDTH  = 1320
    HEIGHT = 820

    def __init__(self) -> None:
        # --- pick API client ------------------------------------------------
        real = RealAPIClient()
        if real.is_alive():
            api_client = real
            mode_label = "LIVE  (FastAPI @ localhost:8000)"
            log.info("Server detected — using RealAPIClient")
        else:
            api_client = MockAPIClient()
            mode_label = "MOCK  (server not running)"
            log.info("Server not running — using MockAPIClient")

        # --- window ---------------------------------------------------------
        self._root = tk.Tk()
        self._root.title(f"{self.TITLE}  [{mode_label}]")
        self._root.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self._root.minsize(900, 600)

        # Style the window background
        self._root.configure(bg="#1a1d23")

        # --- panel ----------------------------------------------------------
        self._panel = TradeIdeasPanel(
            self._root,
            api_client=api_client,
            dry_run=True,
        )
        self._panel.pack(fill="both", expand=True)

        # --- status label at window bottom ----------------------------------
        status_bg = "#0d1117"
        self._foot = tk.Label(
            self._root,
            text=f"Mode: {mode_label}   |   Alt+R Scan   Alt+S Send   F5 Refresh",
            font=("Segoe UI", 8),
            bg=status_bg,
            fg="#7b8299",
            anchor="w",
            padx=8,
        )
        self._foot.pack(fill="x", side="bottom")

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def run(self) -> None:
        self._root.mainloop()

    def _on_close(self) -> None:
        log.info("Closing Trade Ideas panel")
        try:
            self._root.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    app = DemoApp()
    app.run()


if __name__ == "__main__":
    main()
