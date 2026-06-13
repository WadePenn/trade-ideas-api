# tests/test_api.py — Trade Ideas API test suite
#
# Run:
#   py -3.11 -m pytest tests/test_api.py -v
#
# Install test deps first (one-time):
#   py -3.11 -m pip install pytest httpx
#
# No running server needed — uses FastAPI's built-in TestClient.
# All external calls (yfinance, TWS) are mocked so tests run offline.

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────
# Stub out ibapi before anything imports it
# ─────────────────────────────────────────────────────────────────
for mod in ("ibapi", "ibapi.client", "ibapi.wrapper", "ibapi.contract"):
    sys.modules.setdefault(mod, types.ModuleType(mod))

class _EClient: pass   # unique stub — avoids "duplicate base class object"
class _EWrapper: pass
class _Contract: pass

ibapi_client = sys.modules["ibapi.client"]
ibapi_client.EClient = _EClient  # type: ignore

ibapi_wrapper = sys.modules["ibapi.wrapper"]
ibapi_wrapper.EWrapper = _EWrapper  # type: ignore

ibapi_contract = sys.modules["ibapi.contract"]
ibapi_contract.Contract = _Contract  # type: ignore

# ─────────────────────────────────────────────────────────────────
# Now import the app — startup event wires all services
# ─────────────────────────────────────────────────────────────────
from fastapi.testclient import TestClient  # noqa: E402
from main import app                       # noqa: E402

client = TestClient(app)


# ═════════════════════════════════════════════════════════════════
# /  and  /health
# ═════════════════════════════════════════════════════════════════

class TestRoot:
    def test_root_returns_200(self):
        r = client.get("/")
        assert r.status_code == 200

    def test_root_has_service_key(self):
        r = client.get("/")
        assert r.json()["service"] == "Trade Ideas API"

    def test_root_has_docs_link(self):
        r = client.get("/")
        assert "/docs" in r.json()["docs"]


class TestHealth:
    def test_health_200(self):
        r = client.get("/health")
        assert r.status_code == 200, r.text

    def test_health_status_ok(self):
        r = client.get("/health")
        assert r.json()["status"] == "ok"

    def test_health_ibkr_live_is_bool(self):
        """ibkr_live field must be a boolean (True or False)."""
        r = client.get("/health")
        assert isinstance(r.json()["ibkr_live"], bool)

    def test_health_ibkr_connected_null(self):
        """No live connection in test mode → ibkr_connected is null."""
        r = client.get("/health")
        assert r.json()["ibkr_connected"] is None


# ═════════════════════════════════════════════════════════════════
# /market/snapshot/{symbol}
# ═════════════════════════════════════════════════════════════════

# Minimal yfinance Ticker stub
class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.info = {
            "currentPrice":    542.10,
            "bid":             542.08,
            "ask":             542.12,
            "fiftyTwoWeekHigh": 600.00,
            "fiftyTwoWeekLow":  400.00,
        }
        import pandas as pd, numpy as np
        dates = pd.date_range(end="2026-06-12", periods=30, freq="B")
        self.history_df = pd.DataFrame(
            {"Close": np.linspace(500, 542, 30)},
            index=dates,
        )

    def history(self, *args, **kwargs):
        return self.history_df

    def fast_info(self):
        return self.info


@pytest.fixture(autouse=False)
def mock_yfinance():
    with patch("yfinance.Ticker", side_effect=_FakeTicker):
        yield


class TestMarketSnapshot:
    def test_snapshot_200(self, mock_yfinance):
        r = client.get("/market/snapshot/SPY")
        assert r.status_code == 200, r.text

    def test_snapshot_has_required_fields(self, mock_yfinance):
        r = client.get("/market/snapshot/SPY")
        body = r.json()
        for field in ("symbol", "price", "iv30", "hv20", "iv_rank", "price_history"):
            assert field in body, f"Missing field: {field}"

    def test_snapshot_symbol_uppercased(self, mock_yfinance):
        r = client.get("/market/snapshot/spy")
        assert r.json()["symbol"] == "SPY"

    def test_snapshot_price_is_positive(self, mock_yfinance):
        r = client.get("/market/snapshot/SPY")
        assert r.json()["price"] > 0

    def test_snapshot_iv_rank_in_range(self, mock_yfinance):
        r = client.get("/market/snapshot/SPY")
        ivr = r.json()["iv_rank"]
        assert 0.0 <= ivr <= 100.0, f"iv_rank out of range: {ivr}"

    def test_snapshot_price_history_length(self, mock_yfinance):
        r = client.get("/market/snapshot/SPY")
        hist = r.json()["price_history"]
        assert len(hist) >= 5, "price_history too short"

    def test_snapshot_unknown_symbol_returns_error(self, mock_yfinance):
        """A symbol with no price data should return 4xx or an error body."""
        with patch("yfinance.Ticker") as bad:
            t = MagicMock()
            t.info = {}
            t.history.return_value = __import__("pandas").DataFrame()
            bad.return_value = t
            r = client.get("/market/snapshot/XXXXBAD")
            assert r.status_code >= 400 or "error" in r.json()


# ═════════════════════════════════════════════════════════════════
# /ibkr/submit  /ibkr/order/{id}  /ibkr/cancel/{id}
# ═════════════════════════════════════════════════════════════════

VALID_ORDER = {
    "symbol":      "SPY",
    "action":      "BUY",
    "quantity":    1,
    "limit_price": 1.50,
    "account":     "DU_TEST",
    "legs": [
        {
            "symbol":   "SPY",
            "expiry":   "2026-06-19",
            "strike":   540.0,
            "right":    "P",
            "action":   "SELL",
            "ratio":    1,
            "exchange": "SMART",
        },
        {
            "symbol":   "SPY",
            "expiry":   "2026-06-19",
            "strike":   535.0,
            "right":    "P",
            "action":   "BUY",
            "ratio":    1,
            "exchange": "SMART",
        },
    ],
}


class TestIBKRSubmit:
    def test_submit_returns_200(self):
        r = client.post("/ibkr/submit", json=VALID_ORDER)
        assert r.status_code == 200, r.text

    def test_submit_has_order_id(self):
        r = client.post("/ibkr/submit", json=VALID_ORDER)
        assert "order_id" in r.json()

    def test_submit_order_id_is_positive_int(self):
        r = client.post("/ibkr/submit", json=VALID_ORDER)
        assert isinstance(r.json()["order_id"], int)
        assert r.json()["order_id"] > 0

    def test_submit_status_submitted(self):
        r = client.post("/ibkr/submit", json=VALID_ORDER)
        assert r.json()["status"] in ("SUBMITTED", "PENDING")

    def test_submit_no_legs_returns_422(self):
        bad = {**VALID_ORDER, "legs": []}
        r = client.post("/ibkr/submit", json=bad)
        assert r.status_code in (400, 422), r.text

    def test_submit_missing_symbol_returns_422(self):
        bad = {k: v for k, v in VALID_ORDER.items() if k != "symbol"}
        r = client.post("/ibkr/submit", json=bad)
        assert r.status_code == 422


class TestIBKROrderStatus:
    def _submit_and_get_id(self) -> int:
        return client.post("/ibkr/submit", json=VALID_ORDER).json()["order_id"]

    def test_order_status_200(self):
        oid = self._submit_and_get_id()
        r = client.get(f"/ibkr/order/{oid}")
        assert r.status_code == 200, r.text

    def test_order_status_has_order_id(self):
        oid = self._submit_and_get_id()
        r = client.get(f"/ibkr/order/{oid}")
        assert r.json()["order_id"] == oid

    def test_order_status_unknown_id(self):
        r = client.get("/ibkr/order/999999")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json().get("status") in ("INACTIVE", "NOT_FOUND", None)


class TestIBKRCancel:
    def test_cancel_returns_200(self):
        oid = client.post("/ibkr/submit", json=VALID_ORDER).json()["order_id"]
        r = client.post(f"/ibkr/cancel/{oid}")
        assert r.status_code == 200, r.text

    def test_cancel_status_cancelled(self):
        oid = client.post("/ibkr/submit", json=VALID_ORDER).json()["order_id"]
        r = client.post(f"/ibkr/cancel/{oid}")
        assert r.json()["status"] in ("CANCELLED", "PENDING")

    def test_cancel_order_id_matches(self):
        oid = client.post("/ibkr/submit", json=VALID_ORDER).json()["order_id"]
        r = client.post(f"/ibkr/cancel/{oid}")
        assert r.json()["order_id"] == oid


# ═════════════════════════════════════════════════════════════════
# /sell-premium/scan
# ═════════════════════════════════════════════════════════════════

SCAN_PAYLOAD = {
    "symbol":      "SPY",
    "dte_mode":    "Both",
    "max_results": 5,
    "min_score":   0.0,
}


class TestSellPremiumScan:
    def test_scan_200(self, mock_yfinance):
        r = client.post("/sell-premium/scan", json=SCAN_PAYLOAD)
        assert r.status_code == 200, r.text

    def test_scan_has_spreads(self, mock_yfinance):
        r = client.post("/sell-premium/scan", json=SCAN_PAYLOAD)
        body = r.json()
        assert "spreads" in body

    def test_scan_respects_max_results(self, mock_yfinance):
        payload = {**SCAN_PAYLOAD, "max_results": 3}
        r = client.post("/sell-premium/scan", json=payload)
        assert len(r.json()["spreads"]) <= 3

    def test_scan_0dte_mode(self, mock_yfinance):
        r = client.post("/sell-premium/scan", json={**SCAN_PAYLOAD, "dte_mode": "0 DTE"})
        assert r.status_code == 200, r.text
        for spread in r.json()["spreads"]:
            assert spread["dte"] == 0

    def test_scan_7dte_mode(self, mock_yfinance):
        r = client.post("/sell-premium/scan", json={**SCAN_PAYLOAD, "dte_mode": "7 DTE"})
        assert r.status_code == 200, r.text
        for spread in r.json()["spreads"]:
            assert spread["dte"] == 7

    def test_scan_spread_has_required_fields(self, mock_yfinance):
        r = client.post("/sell-premium/scan", json=SCAN_PAYLOAD)
        spreads = r.json()["spreads"]
        if spreads:
            for field in ("score", "grade", "pop", "net_credit_dlr", "max_loss_dlr"):
                assert field in spreads[0], f"Spread missing field: {field}"

    def test_scan_invalid_dte_mode_returns_422(self):
        r = client.post("/sell-premium/scan", json={**SCAN_PAYLOAD, "dte_mode": "99 DTE"})
        assert r.status_code == 422

    def test_scan_missing_symbol_returns_422(self):
        bad = {k: v for k, v in SCAN_PAYLOAD.items() if k != "symbol"}
        r = client.post("/sell-premium/scan", json=bad)
        assert r.status_code == 422


# ═════════════════════════════════════════════════════════════════
# Import smoke tests — catch ModuleNotFoundError before runtime
# ═════════════════════════════════════════════════════════════════

class TestImports:
    def test_import_market_router(self):
        from fastapi_endpoints.routers import market  # noqa: F401

    def test_import_ibkr_router(self):
        from fastapi_endpoints.routers import ibkr  # noqa: F401

    def test_import_sell_premium_router(self):
        from fastapi_endpoints.routers import sell_premium  # noqa: F401

    def test_import_market_service(self):
        from fastapi_endpoints.services import market_data_service  # noqa: F401

    def test_import_ibkr_service(self):
        from fastapi_endpoints.services import ibkr_order_service  # noqa: F401

    def test_import_sell_premium_service(self):
        from fastapi_endpoints.services import sell_premium_service  # noqa: F401

    def test_import_schemas_market(self):
        from fastapi_endpoints.schemas import market  # noqa: F401

    def test_import_schemas_ibkr(self):
        from fastapi_endpoints.schemas import ibkr  # noqa: F401

    def test_import_ibkr_greeks_client(self):
        import ibkr_greeks_client  # noqa: F401 — must not raise ImportError

    def test_sell_premium_scanner_dtemode(self):
        from trade_ideas.sell_premium_scanner import DTEMode
        assert DTEMode.DTE_0 == "0 DTE"
        assert DTEMode.DTE_7 == "7 DTE"
        assert DTEMode.BOTH  == "Both"
