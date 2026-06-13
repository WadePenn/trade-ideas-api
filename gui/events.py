def bind_trade_ideas(tab, api, console):
    def run(trade_type):
        symbol = tab["symbol"].get().strip().upper()
        dte = tab["dte"].get().strip()
        contracts = tab["contracts"].get().strip()

        if not symbol or not dte or not contracts:
            console.insert("end", "Missing input fields\n")
            return

        endpoint = f"/trade-ideas?symbol={symbol}&type={trade_type}&dte={dte}&contracts={contracts}"
        result = api("GET", endpoint)

        tab["results"].delete("1.0", "end")
        tab["results"].insert("end", f"Trade Ideas for {symbol} ({trade_type})\n\n")

        for c in result.get("candidates", []):
            tab["results"].insert("end", f"{c}\n\n")

    # Bind each button
    for trade_type, button in tab["buttons"].items():
        button.config(command=lambda t=trade_type: run(t))

from .utils.refresh import AutoRefresher
from .logger import logger
from .settings_manager import settings

def bind_events(tabs, api, console):
    refresher = AutoRefresher()

    # Import tab initializers
    from .tabs.overview_tab import init_overview_tab
    from .tabs.positions_tab import init_positions_tab
    from .tabs.orders_tab import init_orders_tab
    from .tabs.market_tab import init_market_tab
    from .tabs.trading_tab import init_trading_tab
    from .tabs.settings_tab import init_settings_tab

    # Initialize tabs
    init_overview_tab(tabs["Overview"])
    pos_refresh = init_positions_tab(tabs["Positions"], api, console)
    ord_refresh = init_orders_tab(tabs["Orders"], api, console)
    mkt_refresh = init_market_tab(tabs["Market Data"], api, console)
    trading_refresh = init_trading_tab(tabs["Trading Panel"], api, console)
    init_settings_tab(tabs["Settings"])

    # Auto-refresh intervals from settings
    refresher.add(settings.get("refresh_positions"), pos_refresh)
    refresher.add(settings.get("refresh_orders"), ord_refresh)
    refresher.add(settings.get("refresh_market"), mkt_refresh)

    # Refresh-all callback for hotkeys
    def refresh_all():
        logger.log("Manual refresh triggered")
        pos_refresh()
        ord_refresh()
        mkt_refresh()
        trading_refresh()

    return refresh_all
