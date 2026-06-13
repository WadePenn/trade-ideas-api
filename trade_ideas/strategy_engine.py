"""strategy_engine.py — Scoring engine, trend detection, leg builders."""
from __future__ import annotations
import logging, math, uuid
from datetime import datetime, timedelta
from .models import Greeks, IdeaScore, OptionLeg, StrategyType, TradeIdea, Trend

log = logging.getLogger("trade_ideas.engine")


def _norm(value, lo, hi):
    if hi == lo: return 50.0
    return round(min(max((value - lo) / (hi - lo) * 100, 0.0), 100.0), 2)

def _pop_from_prob_otm(strike, underlying, iv, dte):
    if underlying <= 0 or iv <= 0 or dte <= 0: return 50.0
    T = dte / 365.0
    sig_sqT = iv * math.sqrt(T)
    if sig_sqT == 0: return 50.0
    d2 = (math.log(strike / underlying) + (-0.5 * iv**2) * T) / sig_sqT
    cdf = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2)))
    return round(cdf * 100.0, 1)

def _bs_pop(delta):
    return round((1.0 - abs(delta)) * 100.0, 1)

def _iv_rank_score(iv_rank, seller=True):
    if iv_rank <= 20: s = _norm(iv_rank, 0, 20) * 0.3
    elif iv_rank <= 50: s = _norm(iv_rank, 20, 50) * 0.7 + 10
    elif iv_rank <= 80: s = _norm(iv_rank, 50, 80) * 0.3 + 70
    else: s = 100.0 - _norm(iv_rank, 80, 100) * 0.2
    return s if seller else (100.0 - s)

_TREND_ALIGN = {
    (Trend.BULLISH,  StrategyType.CREDIT_SPREAD): 90.0,
    (Trend.BULLISH,  StrategyType.DEBIT_SPREAD):  85.0,
    (Trend.BULLISH,  StrategyType.IRON_CONDOR):   50.0,
    (Trend.BULLISH,  StrategyType.CALENDAR):      60.0,
    (Trend.BEARISH,  StrategyType.CREDIT_SPREAD): 85.0,
    (Trend.BEARISH,  StrategyType.DEBIT_SPREAD):  90.0,
    (Trend.BEARISH,  StrategyType.IRON_CONDOR):   50.0,
    (Trend.BEARISH,  StrategyType.CALENDAR):      60.0,
    (Trend.NEUTRAL,  StrategyType.IRON_CONDOR):   95.0,
    (Trend.NEUTRAL,  StrategyType.CREDIT_SPREAD): 75.0,
    (Trend.NEUTRAL,  StrategyType.CALENDAR):      80.0,
    (Trend.NEUTRAL,  StrategyType.DEBIT_SPREAD):  40.0,
    (Trend.VOLATILE, StrategyType.DEBIT_SPREAD):  85.0,
    (Trend.VOLATILE, StrategyType.IRON_CONDOR):   30.0,
    (Trend.VOLATILE, StrategyType.CREDIT_SPREAD): 35.0,
    (Trend.VOLATILE, StrategyType.CALENDAR):      55.0,
}

def _liq_score(bid, ask, oi=1000):
    spread_pct = (ask - bid) / ask if ask > 0 else 1.0
    ss = max(0.0, 100.0 - spread_pct * 500)
    ois = min(100.0, math.log1p(oi) / math.log1p(5000) * 100)
    return round(0.6 * ss + 0.4 * ois, 1)

def detect_trend(price_history, iv_rank, hv20, iv30):
    if len(price_history) < 5: return Trend.NEUTRAL
    n = len(price_history)
    xs = list(range(n)); mx = sum(xs)/n; my = sum(price_history)/n
    num = sum((xs[i]-mx)*(price_history[i]-my) for i in range(n))
    den = sum((xs[i]-mx)**2 for i in range(n))
    slope = num/den if den != 0 else 0.0
    slope_pct = slope/my if my else 0.0
    iv_prem = iv30/hv20 if hv20 > 0 else 1.0
    if iv_rank > 70 and iv_prem > 1.3: return Trend.VOLATILE
    if slope_pct > 0.005:  return Trend.BULLISH
    if slope_pct < -0.005: return Trend.BEARISH
    return Trend.NEUTRAL

def auto_select(trend, iv_rank, dte, iv30, hv20):
    iv_prem = iv30/hv20 if hv20 > 0 else 1.0
    if iv_rank >= 50 and trend == Trend.NEUTRAL and 25 <= dte <= 55:
        return StrategyType.IRON_CONDOR
    if iv_rank >= 40 and trend in (Trend.BULLISH, Trend.BEARISH) and dte <= 45:
        return StrategyType.CREDIT_SPREAD
    if iv_rank < 30 and iv_prem < 0.9:
        return StrategyType.CALENDAR
    if iv_rank < 40 and trend in (Trend.BULLISH, Trend.BEARISH):
        return StrategyType.DEBIT_SPREAD
    if trend == Trend.VOLATILE and dte > 40:
        return StrategyType.CALENDAR
    return StrategyType.CREDIT_SPREAD

def aggregate_greeks(legs):
    g = Greeks()
    for leg in legs:
        s = 1.0 if leg.action == "BUY" else -1.0
        q = leg.qty
        g.delta += s * leg.greeks.delta * q
        g.gamma += s * leg.greeks.gamma * q
        g.theta += s * leg.greeks.theta * q
        g.vega  += s * leg.greeks.vega  * q
        g.rho   += s * leg.greeks.rho   * q
    ivs = [l.greeks.iv for l in legs if l.greeks.iv > 0]
    g.iv = sum(ivs)/len(ivs) if ivs else 0.0
    return g

def _expiry(dte, offset=0):
    t = datetime.utcnow() + timedelta(days=dte+offset)
    while t.weekday() != 4: t += timedelta(days=1)
    return t.strftime("%Y%m%d")

def _credit_legs(sym, exp, px, iv, dte, bullish):
    w = round(max(2.0, px*0.02), 0)
    T = dte/365.0; mid_b = round(px*iv*math.sqrt(T)*0.08, 2)
    if bullish:
        ss, ls, r = round(px*0.95,0), round(px*0.95,0)-w, "P"
        sd, ld = -0.25, -0.15
    else:
        ss, ls, r = round(px*1.05,0), round(px*1.05,0)+w, "C"
        sd, ld = 0.25, 0.15
    return [
        OptionLeg(sym, exp, ss, r, "SELL", 1, mid_b,
                  Greeks(sd, 0.02, -0.05, 0.08, 0.0, iv)),
        OptionLeg(sym, exp, ls, r, "BUY",  1, round(mid_b*0.4,2),
                  Greeks(ld, 0.01, 0.02, -0.04, 0.0, iv*1.05)),
    ]

def _debit_legs(sym, exp, px, iv, dte, bullish):
    w = round(max(2.0, px*0.02), 0)
    T = dte/365.0; atm_mid = round(px*iv*math.sqrt(T)*0.10, 2)
    if bullish:
        atm, otm, r, bd, sd = round(px,0), round(px,0)+w, "C", 0.50, 0.30
    else:
        atm, otm, r, bd, sd = round(px,0), round(px,0)-w, "P", -0.50, -0.30
    return [
        OptionLeg(sym, exp, atm, r, "BUY",  1, atm_mid,
                  Greeks(bd, 0.03, -0.08, 0.12, 0.0, iv)),
        OptionLeg(sym, exp, otm, r, "SELL", 1, round(atm_mid*0.5,2),
                  Greeks(sd, 0.02, 0.04, -0.06, 0.0, iv*1.02)),
    ]

def _condor_legs(sym, exp, px, iv, dte):
    w = round(max(2.0, px*0.02), 0)
    cs, cb = round(px*1.05,0), round(px*1.05,0)+w
    ps, pb = round(px*0.95,0), round(px*0.95,0)-w
    T = dte/365.0; mb = round(px*iv*math.sqrt(T)*0.06, 2)
    return [
        OptionLeg(sym,exp,pb,"P","BUY", 1,round(mb*0.3,2),Greeks(-0.10,0.01, 0.02,-0.03,0,iv*1.08)),
        OptionLeg(sym,exp,ps,"P","SELL",1,round(mb*0.6,2),Greeks(-0.20,0.02,-0.04, 0.06,0,iv*1.04)),
        OptionLeg(sym,exp,cs,"C","SELL",1,round(mb*0.6,2),Greeks( 0.20,0.02,-0.04, 0.06,0,iv*1.04)),
        OptionLeg(sym,exp,cb,"C","BUY", 1,round(mb*0.3,2),Greeks( 0.10,0.01, 0.02,-0.03,0,iv*1.08)),
    ]

def _calendar_legs(sym, ne, fe, px, iv, dte):
    sk = round(px, 0)
    Tn = max(dte-14,7)/365.0; Tf = dte/365.0
    nm = round(px*iv*math.sqrt(Tn)*0.09, 2); fm = round(px*iv*math.sqrt(Tf)*0.12, 2)
    return [
        OptionLeg(sym,ne,sk,"C","SELL",1,nm,Greeks(0.50,0.03,-0.12,0.10,0,iv)),
        OptionLeg(sym,fe,sk,"C","BUY", 1,fm,Greeks(0.50,0.02,-0.07,0.18,0,iv*0.97)),
    ]


class StrategyEngine:
    def _score_idea(self, legs, strategy, pop, iv_rank, trend, max_profit, max_loss):
        seller = strategy in (StrategyType.CREDIT_SPREAD, StrategyType.IRON_CONDOR)
        rr_s = min((max_profit / abs(max_loss) * 25) if max_loss else 0.0, 100.0)
        liq_s = sum(_liq_score(l.mid_price*0.95, l.mid_price*1.05) for l in legs) / max(len(legs),1)
        return IdeaScore(
            pop_score       = _norm(pop, 40, 85),
            iv_rank_score   = _iv_rank_score(iv_rank, seller),
            trend_score     = _TREND_ALIGN.get((trend, strategy), 50.0),
            reward_risk     = rr_s,
            liquidity_score = liq_s,
        )

    def _build(self, sym, strat, dte, contracts, px, iv, iv_rank, iv_pct, trend, hv20):
        ne = _expiry(dte); fe = _expiry(dte, 14)
        bull = (trend == Trend.BULLISH)
        if strat == StrategyType.CREDIT_SPREAD:
            legs = _credit_legs(sym, ne, px, iv, dte, bull)
        elif strat == StrategyType.DEBIT_SPREAD:
            legs = _debit_legs(sym, ne, px, iv, dte, bull)
        elif strat == StrategyType.IRON_CONDOR:
            legs = _condor_legs(sym, ne, px, iv, dte)
        else:
            legs = _calendar_legs(sym, ne, fe, px, iv, dte)

        net = sum((l.mid_price if l.action=="SELL" else -l.mid_price)*l.qty for l in legs)*100*contracts
        w = abs(legs[0].strike - legs[1].strike) if len(legs) >= 2 else 5.0

        if strat == StrategyType.CREDIT_SPREAD:
            mp, ml = net, -(w*100*contracts - net)
        elif strat == StrategyType.DEBIT_SPREAD:
            mp, ml = w*100*contracts + net, net
        elif strat == StrategyType.IRON_CONDOR:
            mp, ml = net, -(w*100*contracts - net)
        else:
            mp, ml = abs(net)*2, net

        short_legs = [l for l in legs if l.action=="SELL"]
        pop = sum(_bs_pop(l.greeks.delta) for l in short_legs) / max(len(short_legs),1)
        score = self._score_idea(legs, strat, pop, iv_rank, trend, mp, abs(ml))
        ng = aggregate_greeks(legs)

        return TradeIdea(
            id=str(uuid.uuid4())[:8], symbol=sym, strategy=strat,
            dte=dte, contracts=contracts, legs=legs, score=score,
            net_credit=round(net,2), max_profit=round(mp,2), max_loss=round(ml,2),
            pop=round(pop,1), iv_rank=iv_rank, iv_pct=iv_pct,
            trend=trend, underlying_px=px, net_greeks=ng,
        )

    def generate(self, symbol, dte, contracts, strategy, market_data):
        px      = float(market_data.get("underlying_price", 100.0))
        iv30    = float(market_data.get("iv30",   0.25))
        hv20    = float(market_data.get("hv20",   0.20))
        iv_rank = float(market_data.get("iv_rank", 50.0))
        iv_pct  = float(market_data.get("iv_pct",  50.0))
        hist    = market_data.get("price_history", [px]*10)
        trend   = detect_trend(hist, iv_rank, hv20, iv30)
        ideas   = []

        candidates = ([StrategyType.CREDIT_SPREAD, StrategyType.DEBIT_SPREAD,
                       StrategyType.IRON_CONDOR,   StrategyType.CALENDAR]
                      if strategy == StrategyType.AUTO else [strategy])

        for strat in candidates:
            try:
                idea = self._build(symbol, strat, dte, contracts, px, iv30, iv_rank, iv_pct, trend, hv20)
                ideas.append(idea)
            except Exception as e:
                log.warning("Build %s failed: %s", strat, e)

        ideas.sort(key=lambda i: i.score.composite, reverse=True)
        if strategy == StrategyType.AUTO:
            ideas = ideas[:3]
        if ideas:
            ideas[0].notes = "★ Best Fit"
        log.info("Generated %d idea(s) for %s | trend=%s | ivr=%.1f", len(ideas), symbol, trend.value, iv_rank)
        return ideas
