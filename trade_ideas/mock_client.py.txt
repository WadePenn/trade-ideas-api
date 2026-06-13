# trade_ideas/mock_client.py — MockAPIClient for offline/dev mode.
# Returns realistic fake market data so the panel works without a server.

from __future__ import annotations

import math
import random
from typing import Any, Dict, Optional


class MockAPIClient:
    """
    Simulates the FastAPI backend locally.
    No network calls — all data is generated in memory.
    The panel uses this automatically when the real server is not running.
    """

    # Realistic base prices for common tickers
    _PRICES = {
        "SPY":  545.0, "QQQ":  480.0, "IWM":  215.0,
        "AAPL": 215.0, "TSLA": 310.0, "NVDA": 870.0,
        "AMZN": 195.0, "MSFT": 435.0, "META": 580.0,
        "GOOG": 175.0, "AMD":  165.0, "NFLX": 640.0,
    }

    def get(self, path: str, timeout: float = 8.0, **kw) -> Optional[Dict[str, Any]]:
        """Dispatch GET path to the appropriate mock handler."""
        if path.startswith("/market/snapshot/"):
            symbol = path.split("/")[-1].upper()
            return self._snapshot(symbol)
        if path.startswith("/health"):
            return {"status": "ok"}
        return None

    def post(self, path: str, json: Optional[dict] = None,
             timeout: float = 10.0, **kw) -> Optional[Dict[str, Any]]:
        """Dispatch POST path to the appropriate mock handler."""
        if path == "/ibkr/submit":
            return self._submit_order(json or {})
        if path.startswith("/ibkr/cancel/"):
            oid = int(path.split("/")[-1])
            return {"order_id": oid, "status": "CANCELLED", "message": "Cancelled (mock)"}
        if path == "/sell-premium/scan":
            return self._sell_premium_scan(json or {})
        return None

    # ── market snapshot ────────────────────────────────────────────

    def _snapshot(self, symbol: str) -> dict:
        rng   = random.Random(hash(symbol) ^ 42)
        base  = self._PRICES.get(symbol, 100.0)
        price = round(base * rng.uniform(0.97, 1.03), 2)
        iv30  = round(rng.uniform(0.15, 0.55), 3)
        hv20  = round(iv30 * rng.uniform(0.70, 1.15), 3)
        ivr   = round(rng.uniform(20, 85), 1)

        history = []
        p = price
        for _ in range(25):
            p = round(p * (1 + rng.uniform(-0.008, 0.008)), 2)
            history.append(p)
        history.reverse()

        return {
            "symbol":        symbol,
            "price":         price,
            "iv30":          iv30,
            "hv20":          hv20,
            "iv_rank":       ivr,
            "iv_pct":        round(ivr * rng.uniform(0.80, 1.10), 1),
            "price_history": history,
            "bid":           round(price - 0.02, 2),
            "ask":           round(price + 0.02, 2),
        }

    # ── IBKR order simulation ──────────────────────────────────────

    _next_id = 10001

    def _submit_order(self, payload: dict) -> dict:
        oid = MockAPIClient._next_id
        MockAPIClient._next_id += 1
        return {
            "order_id": oid,
            "account":  payload.get("account", "DU_DEMO"),
            "status":   "SUBMITTED",
        }

    # ── sell-premium mock scan ─────────────────────────────────────

    def _sell_premium_scan(self, payload: dict) -> dict:
        import uuid, datetime
        sym  = payload.get("symbol", "SPY").upper()
        snap = self._snapshot(sym)
        S    = snap["price"]
        iv   = snap["iv30"]
        ivr  = snap["iv_rank"]

        spreads = []
        rng = random.Random(hash(sym) ^ 99)
        step = max(1.0, round(S * 0.005))

        for dte in ([0] if payload.get("dte_mode") == "0 DTE"
                    else [7] if payload.get("dte_mode") == "7 DTE"
                    else [0, 7]):
            for right in ("P", "C"):
                for i in range(3):
                    d       = rng.uniform(0.10, 0.28)
                    short_k = round(S * (1 - d * 0.8) if right == "P"
                                    else S * (1 + d * 0.8), 1)
                    long_k  = round(short_k - step * 2 if right == "P"
                                    else short_k + step * 2, 1)
                    width   = abs(short_k - long_k)
                    credit  = round(rng.uniform(0.20, 0.60) * width, 2)
                    pop     = round(rng.uniform(62, 85), 1)
                    score   = round(rng.uniform(50, 92), 1)
                    grade   = ("A" if score >= 80 else "B" if score >= 65
                               else "C" if score >= 50 else "D")
                    cw      = round(credit / width, 3) if width else 0

                    from datetime import date, timedelta
                    exp = (date.today() + timedelta(days=dte)).strftime("%Y%m%d")

                    spreads.append({
                        "id":                 str(uuid.uuid4())[:8].upper(),
                        "symbol":             sym,
                        "dte":                dte,
                        "right":              right,
                        "short_strike":       short_k,
                        "long_strike":        long_k,
                        "expiry":             exp,
                        "net_credit_dlr":     round(credit * 100, 2),
                        "max_loss_dlr":       round((width - credit) * 100, 2),
                        "width_pts":          width,
                        "credit_width_ratio": cw,
                        "pop":                pop,
                        "score":              score,
                        "grade":              grade,
                        "short_delta":        round(-d if right == "P" else d, 3),
                        "net_gamma":          round(-rng.uniform(0.01, 0.06), 4),
                        "net_theta":          round(rng.uniform(0.02, 0.12), 4),
                        "net_vega":           round(-rng.uniform(0.05, 0.20), 4),
                        "short_iv":           round(iv * rng.uniform(0.9, 1.1), 3),
                        "short_oi":           rng.randint(100, 5000),
                        "long_oi":            rng.randint(50, 3000),
                        "notes":              (
                            f"{'0DTE' if dte == 0 else '7DTE'} "
                            f"{'Put CS' if right == 'P' else 'Call CS'} | "
                            f"Short {right}{short_k} / Long {right}{long_k} | "
                            f"C/W {cw:.0%}"
                        ),
                    })

        spreads.sort(key=lambda x: x["score"], reverse=True)
        return {
            "symbol":      sym,
            "dte_mode":    payload.get("dte_mode", "Both"),
            "scan_time":   datetime.datetime.utcnow().isoformat() + "Z",
            "iv_rank":     ivr,
            "iv30":        iv,
            "underlying":  S,
            "total_found": len(spreads),
            "spreads":     spreads[:payload.get("max_results", 10)],
        }
