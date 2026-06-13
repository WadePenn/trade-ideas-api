"""ibkr_bridge.py — IBKR order routing via FastAPI backend."""
from __future__ import annotations
import logging, threading, time
from typing import Callable, Optional
from .models import TradeIdea, IdeaStatus

log = logging.getLogger("trade_ideas.ibkr")

def build_ibkr_payload(idea: TradeIdea, account: str = "") -> dict:
    is_credit = idea.net_credit >= 0
    limit_price = abs(round(idea.net_credit / max(idea.contracts * 100, 1), 2))
    return {
        "account":    account,
        "symbol":     idea.symbol,
        "sec_type":   "BAG",
        "exchange":   "SMART",
        "currency":   "USD",
        "action":     "SELL" if is_credit else "BUY",
        "quantity":   idea.contracts,
        "order_type": "LMT",
        "limit_price": limit_price,
        "tif":        "DAY",
        "strategy":   idea.strategy.value,
        "legs": [{"symbol": l.symbol, "expiry": l.expiry, "strike": l.strike,
                  "right": l.right, "action": l.action, "ratio": l.qty,
                  "exchange": "SMART", "currency": "USD", "sec_type": "OPT"}
                 for l in idea.legs],
        "client_tag": f"TI-{idea.id}",
        "meta": {"idea_id": idea.id, "pop": idea.pop,
                 "score": idea.score.composite, "max_loss": idea.max_loss},
    }

class IBKRBridge:
    def __init__(self, api_client=None, dry_run=False,
                 on_status: Optional[Callable]=None, account=""):
        self._api       = api_client
        self._dry_run   = dry_run
        self._on_status = on_status
        self._account   = account

    def submit(self, idea: TradeIdea) -> bool:
        payload = build_ibkr_payload(idea, self._account)
        if self._dry_run:
            log.info("[DRY-RUN] Would submit: %s", payload.get("strategy"))
            idea.status = IdeaStatus.SENT
            idea.ibkr_order_id = 99999
            idea.ibkr_account  = "DU_DEMO"
            self._notify(idea.id, IdeaStatus.SENT)
            return True
        try:
            resp = self._api.post("/ibkr/submit", json=payload, timeout=10)
            if resp and resp.get("order_id"):
                idea.ibkr_order_id = int(resp["order_id"])
                idea.ibkr_account  = resp.get("account", self._account)
                idea.status        = IdeaStatus.SENT
                self._notify(idea.id, IdeaStatus.SENT)
                threading.Thread(target=self._poll, args=(idea,), daemon=True).start()
                return True
        except Exception as e:
            log.error("Submit failed: %s", e)
        idea.status = IdeaStatus.REJECTED
        self._notify(idea.id, IdeaStatus.REJECTED)
        return False

    def cancel(self, idea: TradeIdea) -> bool:
        if not idea.ibkr_order_id:
            return False
        if self._dry_run:
            idea.status = IdeaStatus.CANCELLED
            self._notify(idea.id, IdeaStatus.CANCELLED)
            return True
        try:
            self._api.post(f"/ibkr/cancel/{idea.ibkr_order_id}", timeout=5)
            idea.status = IdeaStatus.CANCELLED
            self._notify(idea.id, IdeaStatus.CANCELLED)
            return True
        except Exception as e:
            log.error("Cancel failed: %s", e)
            return False

    def set_account(self, acct): self._account = acct
    def set_dry_run(self, v):    self._dry_run = v; log.info("dry_run=%s", v)

    def _notify(self, idea_id, status):
        if self._on_status:
            try: self._on_status(idea_id, status)
            except Exception as e: log.warning("Status cb error: %s", e)

    def _poll(self, idea, interval=5, max_polls=24):
        for _ in range(max_polls):
            time.sleep(interval)
            if idea.status in (IdeaStatus.FILLED, IdeaStatus.CANCELLED):
                break
            try:
                r = self._api.get(f"/ibkr/order/{idea.ibkr_order_id}", timeout=5)
                if r:
                    s = r.get("status","").upper()
                    if s == "FILLED":
                        idea.status = IdeaStatus.FILLED
                        self._notify(idea.id, IdeaStatus.FILLED); break
                    elif s in ("CANCELLED","INACTIVE"):
                        idea.status = IdeaStatus.CANCELLED
                        self._notify(idea.id, IdeaStatus.CANCELLED); break
            except Exception as e:
                log.debug("Poll error: %s", e)
