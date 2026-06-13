"""api_adapter.py — Wraps your APIClient; MockAPIClient for dev/testing."""
from __future__ import annotations
import logging, random, math
from typing import Any, Optional

log = logging.getLogger("trade_ideas.api")

class TradeIdeasAPIAdapter:
    """Pass your existing api_client.APIClient instance here."""
    def __init__(self, client):
        self._c = client

    def get(self, path, timeout=8, **kw) -> Optional[dict]:
        try:
            if hasattr(self._c, "get"):   return self._c.get(path, timeout=timeout, **kw)
            if hasattr(self._c, "fetch"): return self._c.fetch(path, **kw)
        except Exception as e:
            log.warning("GET %s: %s", path, e)
        return None

    def post(self, path, json=None, timeout=10, **kw) -> Optional[dict]:
        try:
            if hasattr(self._c, "post"): return self._c.post(path, json=json, timeout=timeout, **kw)
            if hasattr(self._c, "send"): return self._c.send(path, json=json, **kw)
        except Exception as e:
            log.warning("POST %s: %s", path, e)
        return None


class MockAPIClient:
    """Realistic mock — no live backend needed."""

    _PRICES = {"SPY":545.0,"QQQ":480.0,"IWM":215.0,"AAPL":215.0,
               "TSLA":310.0,"NVDA":870.0,"AMZN":195.0,"MSFT":435.0}

    def get(self, path, timeout=8, **kw) -> dict:
        if "/market/snapshot/" in path:
            sym = path.rstrip("/").split("/")[-1].upper()
            px  = self._PRICES.get(sym, 100.0) + random.uniform(-3, 3)
            iv30    = round(random.uniform(0.15, 0.45), 3)
            hv20    = round(iv30 * random.uniform(0.7, 1.2), 3)
            iv_rank = round(random.uniform(20, 85), 1)
            hist    = [px*(1+random.uniform(-0.005,0.005)) for _ in range(20)]
            return {"symbol":sym,"price":round(px,2),"iv30":iv30,"hv20":hv20,
                    "iv_rank":iv_rank,"iv_pct":round(random.uniform(25,80),1),
                    "price_history":hist}
        if "/ibkr/order/" in path:
            return {"status": random.choice(["SUBMITTED","SUBMITTED","FILLED"]), "filled_qty":0}
        return {}

    def post(self, path, json=None, timeout=10, **kw) -> dict:
        if "/ibkr/submit" in path:
            return {"order_id":random.randint(10000,99999),"account":"DU_MOCK","status":"SUBMITTED"}
        if "/ibkr/cancel/" in path:
            return {"status":"CANCELLED"}
        return {}
