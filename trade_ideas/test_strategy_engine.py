"""
tests/test_strategy_engine.py
Run with:  python -m pytest trade_ideas/tests/ -v
or:        python trade_ideas/tests/test_strategy_engine.py
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import unittest
from trade_ideas.models import StrategyType, Trend, IdeaScore
from trade_ideas.strategy_engine import (
    StrategyEngine, detect_trend,
    _pop_from_prob_otm, _norm,
)
from trade_ideas.ibkr_bridge import build_ibkr_payload
from trade_ideas.api_adapter import MockAPIClient
from trade_ideas.events_bridge import wrap_event_bus
from trade_ideas.hotkey_adapter import HotkeyAdapter, HOTKEYS
from trade_ideas.logger_setup import get_logger
import logging


# ─── fixtures ─────────────────────────────────────────────────────────────────
ENGINE = StrategyEngine()

MARKET = {
    "underlying_price": 545.0,
    "iv30": 0.28,
    "hv20": 0.20,
    "iv_rank": 62.0,
    "iv_pct": 58.0,
    "price_history": [540 + i * 0.5 for i in range(15)],
}


# ─── IdeaScore ─────────────────────────────────────────────────────────────────
class TestIdeaScore(unittest.TestCase):

    def test_composite_in_range(self):
        s = IdeaScore(pop_score=80, iv_rank_score=70,
                      trend_score=90, reward_risk=60, liquidity_score=75)
        self.assertGreaterEqual(s.composite, 0)
        self.assertLessEqual(s.composite, 100)

    def test_grade_valid(self):
        s = IdeaScore(pop_score=80, iv_rank_score=70,
                      trend_score=90, reward_risk=60, liquidity_score=75)
        self.assertIn(s.grade, ("A", "B", "C", "D", "F"))

    def test_all_zero_is_F(self):
        self.assertEqual(IdeaScore().grade, "F")

    def test_all_max_is_A(self):
        s = IdeaScore(pop_score=100, iv_rank_score=100,
                      trend_score=100, reward_risk=100, liquidity_score=100)
        self.assertEqual(s.grade, "A")
        self.assertAlmostEqual(s.composite, 100.0, places=1)

    def test_color_tag_exists(self):
        s = IdeaScore(pop_score=60, iv_rank_score=55,
                      trend_score=70, reward_risk=50, liquidity_score=60)
        self.assertIn(s.color_tag, ("score_poor", "score_fair", "score_good", "score_excellent"))


# ─── _norm ─────────────────────────────────────────────────────────────────────
class TestNorm(unittest.TestCase):

    def test_midpoint(self):
        self.assertAlmostEqual(_norm(50, 0, 100), 50.0)

    def test_clamp_low(self):
        self.assertAlmostEqual(_norm(-999, 0, 100), 0.0)

    def test_clamp_high(self):
        self.assertAlmostEqual(_norm(999, 0, 100), 100.0)

    def test_equal_bounds_returns_50(self):
        # Equal lo/hi is degenerate; implementation returns 50.0 (midpoint)
        self.assertAlmostEqual(_norm(50, 50, 50), 50.0)


# ─── POP ───────────────────────────────────────────────────────────────────────
class TestPOP(unittest.TestCase):

    def test_deep_otm_high(self):
        v = _pop_from_prob_otm(underlying=500, strike=600, iv=0.25, dte=30)
        self.assertGreater(v, 70, f"expected >70, got {v:.2f}")

    def test_deep_itm_low(self):
        v = _pop_from_prob_otm(underlying=500, strike=400, iv=0.25, dte=30)
        self.assertLess(v, 30, f"expected <30, got {v:.2f}")

    def test_atm_near_50(self):
        v = _pop_from_prob_otm(underlying=500, strike=500, iv=0.25, dte=30)
        self.assertAlmostEqual(v, 50, delta=8)

    def test_zero_dte_returns_50(self):
        v = _pop_from_prob_otm(underlying=500, strike=550, iv=0.25, dte=0)
        self.assertEqual(v, 50.0)

    def test_zero_iv_returns_50(self):
        v = _pop_from_prob_otm(underlying=500, strike=550, iv=0.0, dte=30)
        self.assertEqual(v, 50.0)


# ─── Trend ─────────────────────────────────────────────────────────────────────
class TestTrend(unittest.TestCase):

    def test_bullish(self):
        prices = [100 + i * 2 for i in range(15)]
        t = detect_trend(prices, iv_rank=40, hv20=0.18, iv30=0.18)
        self.assertEqual(t, Trend.BULLISH)

    def test_bearish(self):
        prices = [200 - i * 3 for i in range(15)]
        t = detect_trend(prices, iv_rank=35, hv20=0.18, iv30=0.18)
        self.assertEqual(t, Trend.BEARISH)

    def test_volatile(self):
        # iv_rank > 70 AND iv_prem (iv30/hv20) > 1.3 => VOLATILE
        prices = [100] * 15
        t = detect_trend(prices, iv_rank=80, hv20=0.25, iv30=0.40)  # iv_prem=1.6
        self.assertEqual(t, Trend.VOLATILE)

    def test_neutral(self):
        prices = [100 + i % 2 * 0.5 for i in range(15)]
        t = detect_trend(prices, iv_rank=40, hv20=0.22, iv30=0.20)
        self.assertEqual(t, Trend.NEUTRAL)

    def test_short_history(self):
        t = detect_trend([100, 101], iv_rank=40, hv20=0.22, iv30=0.20)
        self.assertIsInstance(t, Trend)


# ─── Strategy Engine ───────────────────────────────────────────────────────────
class TestStrategyEngine(unittest.TestCase):

    def test_auto_returns_ideas(self):
        ideas = ENGINE.generate("SPY", 30, 1, StrategyType.AUTO, MARKET)
        self.assertGreater(len(ideas), 0)

    def test_auto_first_marked(self):
        ideas = ENGINE.generate("SPY", 30, 1, StrategyType.AUTO, MARKET)
        self.assertTrue(ideas[0].notes.startswith("★"))

    def test_auto_sorted_descending(self):
        ideas = ENGINE.generate("SPY", 30, 1, StrategyType.AUTO, MARKET)
        scores = [i.score.composite for i in ideas]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_auto_score_in_range(self):
        ideas = ENGINE.generate("SPY", 30, 1, StrategyType.AUTO, MARKET)
        for idea in ideas:
            self.assertGreaterEqual(idea.score.composite, 0)
            self.assertLessEqual(idea.score.composite, 100)

    def test_credit_spread_type(self):
        r = ENGINE.generate("SPY", 30, 1, StrategyType.CREDIT_SPREAD, MARKET)
        self.assertTrue(r)
        self.assertEqual(r[0].strategy, StrategyType.CREDIT_SPREAD)

    def test_debit_spread_type(self):
        r = ENGINE.generate("SPY", 30, 1, StrategyType.DEBIT_SPREAD, MARKET)
        self.assertTrue(r)
        self.assertEqual(r[0].strategy, StrategyType.DEBIT_SPREAD)

    def test_iron_condor_type(self):
        r = ENGINE.generate("SPY", 30, 1, StrategyType.IRON_CONDOR, MARKET)
        self.assertTrue(r)
        self.assertEqual(r[0].strategy, StrategyType.IRON_CONDOR)

    def test_calendar_type(self):
        r = ENGINE.generate("SPY", 30, 1, StrategyType.CALENDAR, MARKET)
        self.assertTrue(r)
        self.assertEqual(r[0].strategy, StrategyType.CALENDAR)

    def test_iron_condor_four_legs(self):
        r = ENGINE.generate("SPY", 35, 1, StrategyType.IRON_CONDOR, MARKET)
        self.assertEqual(len(r[0].legs), 4)

    def test_iron_condor_delta_near_zero(self):
        r = ENGINE.generate("SPY", 35, 1, StrategyType.IRON_CONDOR, MARKET)
        self.assertLess(abs(r[0].net_greeks.delta), 0.20)

    def test_credit_spread_positive_theta(self):
        r = ENGINE.generate("SPY", 30, 1, StrategyType.CREDIT_SPREAD, MARKET)
        self.assertGreater(r[0].net_greeks.theta, 0)

    def test_contracts_multiplier(self):
        r1 = ENGINE.generate("SPY", 30, 1, StrategyType.CREDIT_SPREAD, MARKET)
        r5 = ENGINE.generate("SPY", 30, 5, StrategyType.CREDIT_SPREAD, MARKET)
        ratio = r5[0].net_credit / r1[0].net_credit
        self.assertAlmostEqual(ratio, 5.0, places=2)


# ─── IBKR Bridge ───────────────────────────────────────────────────────────────
class TestIBKRBridge(unittest.TestCase):

    def _idea(self):
        return ENGINE.generate("SPY", 30, 1, StrategyType.AUTO, MARKET)[0]

    def test_symbol(self):
        p = build_ibkr_payload(self._idea(), "DU999")
        self.assertEqual(p["symbol"], "SPY")

    def test_leg_count(self):
        idea = self._idea()
        p = build_ibkr_payload(idea, "DU999")
        self.assertEqual(len(p["legs"]), len(idea.legs))

    def test_order_type_lmt(self):
        self.assertEqual(build_ibkr_payload(self._idea(), "DU999")["order_type"], "LMT")

    def test_tif_day(self):
        self.assertEqual(build_ibkr_payload(self._idea(), "DU999")["tif"], "DAY")

    def test_meta_has_pop(self):
        self.assertIn("pop", build_ibkr_payload(self._idea(), "DU999")["meta"])


# ─── MockAPIClient ─────────────────────────────────────────────────────────────
class TestMockAPIClient(unittest.TestCase):

    def setUp(self):
        self.client = MockAPIClient()

    def test_snapshot_price(self):
        snap = self.client.get("/market/snapshot/SPY")
        self.assertGreater(snap["price"], 0)

    def test_snapshot_iv_rank(self):
        snap = self.client.get("/market/snapshot/SPY")
        self.assertGreater(snap["iv_rank"], 0)
        self.assertLessEqual(snap["iv_rank"], 100)

    def test_submit_order_id(self):
        r = self.client.post("/ibkr/submit", json={})
        self.assertIn("order_id", r)

    def test_submit_status(self):
        r = self.client.post("/ibkr/submit", json={})
        self.assertEqual(r["status"], "SUBMITTED")

    def test_cancel_status(self):
        r = self.client.post("/ibkr/cancel/1")
        self.assertEqual(r["status"], "CANCELLED")


# ─── EventBusShim ─────────────────────────────────────────────────────────────
class TestEventBusShim(unittest.TestCase):

    def test_wrap_none_returns_none(self):
        self.assertIsNone(wrap_event_bus(None))

    def test_subscribe_publish(self):
        calls = []
        class FakeBus:
            def subscribe(self, e, cb): calls.append(("sub", e))
            def publish(self, e, d=None): calls.append(("pub", e))
        shim = wrap_event_bus(FakeBus())
        shim.subscribe("X", lambda d: None)
        shim.publish("X", {})
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], "sub")
        self.assertEqual(calls[1][0], "pub")

    def test_on_emit_variant(self):
        calls = []
        class FakeBus2:
            def on(self, e, cb): calls.append("on")
            def emit(self, e, d=None): calls.append("emit")
        shim = wrap_event_bus(FakeBus2())
        shim.subscribe("Y", lambda d: None)
        shim.publish("Y", {})
        self.assertEqual(calls, ["on", "emit"])


# ─── HotkeyAdapter ────────────────────────────────────────────────────────────
class TestHotkeyAdapter(unittest.TestCase):

    def test_hotkeys_defined(self):
        self.assertIn("alt+r", HOTKEYS)
        self.assertIn("alt+s", HOTKEYS)
        self.assertIn("f5",    HOTKEYS)

    def test_register_api(self):
        registered = []
        class FakeMgr:
            def register(self, combo, cb, description=""):
                registered.append(combo)
        hk = HotkeyAdapter(FakeMgr())
        hk.register("alt+r", lambda: None)
        self.assertIn("alt+r", registered)

    def test_bind_api(self):
        bound = []
        class FakeMgr2:
            def bind(self, combo, cb): bound.append(combo)
        hk = HotkeyAdapter(FakeMgr2())
        hk.register("alt+s", lambda: None)
        self.assertIn("alt+s", bound)

    def test_none_manager_no_crash(self):
        # HotkeyAdapter(None) has no recognised API — ensure it warns
        # rather than crashing on construction; registration raises AttributeError
        hk = HotkeyAdapter(None)
        with self.assertRaises(AttributeError):
            hk.register("f5", lambda: None)


# ─── Logger ───────────────────────────────────────────────────────────────────
class TestLogger(unittest.TestCase):

    def test_name(self):
        lg = get_logger(level=logging.WARNING, enable_console=False)
        self.assertEqual(lg.name, "trade_ideas")

    def test_set_level(self):
        from trade_ideas.logger_setup import set_level
        lg = get_logger(level=logging.WARNING, enable_console=False)
        set_level(logging.DEBUG)
        self.assertEqual(lg.level, logging.DEBUG)
        set_level(logging.WARNING)   # restore


if __name__ == "__main__":
    unittest.main(verbosity=2)
