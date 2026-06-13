# ideas/trade_builder.py

def build_trade_candidates(symbol, trade_type, dte, chain, contracts):
    """
    Build ranked option trade candidates for a given symbol, trade type, and DTE.
    chain = list of option records from IBKR with fields:
        - strike
        - right ("C" or "P")
        - expiry
        - dte
        - bid
        - ask
        - delta
    """

    # ---------------------------------------------------------
    # FILTER CHAIN BY DTE
    # ---------------------------------------------------------
    filtered = [c for c in chain if c.get("dte") == dte]

    candidates = []

    # ---------------------------------------------------------
    # CREDIT SPREADS (CALL SIDE)
    # ---------------------------------------------------------
    if trade_type == "credit":
        for opt in filtered:
            if opt["right"] != "C":
                continue

            short_strike = opt["strike"]
            long_strike = short_strike + 5

            credit = round(opt["bid"] * 0.9, 2)
            pop = round(1 - opt.get("delta", 0.5), 2)

            candidates.append({
                "structure": "credit_call_spread",
                "symbol": symbol,
                "expiry": opt["expiry"],
                "dte": dte,
                "contracts": contracts,
                "short": short_strike,
                "long": long_strike,
                "credit": credit,
                "pop": pop,
                "notes": "High POP credit spread candidate"
            })

    # ---------------------------------------------------------
    # DEBIT SPREADS (CALL SIDE)
    # ---------------------------------------------------------
    if trade_type == "debit":
        for opt in filtered:
            if opt["right"] != "C":
                continue

            long_strike = opt["strike"]
            short_strike = long_strike + 5

            debit = round(opt["ask"] * 1.1, 2)

            candidates.append({
                "structure": "debit_call_spread",
                "symbol": symbol,
                "expiry": opt["expiry"],
                "dte": dte,
                "contracts": contracts,
                "long": long_strike,
                "short": short_strike,
                "debit": debit,
                "rr_ratio": 2.0,
                "notes": "Directional debit spread candidate"
            })

    # ---------------------------------------------------------
    # IRON CONDOR (simple neutral template)
    # ---------------------------------------------------------
    if trade_type == "condor":
        # You can expand this later with real chain logic
        candidates.append({
            "structure": "iron_condor",
            "symbol": symbol,
            "dte": dte,
            "contracts": contracts,
            "wings": "5-wide",
            "credit": 1.20,
            "pop": 0.68,
            "notes": "Neutral IV-based condor"
        })

    # ---------------------------------------------------------
    # CALENDAR SPREAD (simple template)
    # ---------------------------------------------------------
    if trade_type == "calendar":
        if filtered:
            strike = filtered[0]["strike"]
            candidates.append({
                "structure": "calendar",
                "symbol": symbol,
                "dte": dte,
