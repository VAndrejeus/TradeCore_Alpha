from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from app.clients.alpaca_market_data import AlpacaMarketDataClient
from app.clients.finnhub_news import FinnhubNewsClient
from app.config import Settings
from app.models.watchlist import Watchlist
from app.services.catalyst_service import CatalystService
from app.services.risk_service import RiskService
from app.services.scan_service import ScanService
from app.services.sentiment_service import SentimentService
from app.services.signal_service import SignalService
from app.services.watchlist_service import WatchlistService


EASTERN_TZ = ZoneInfo("America/New_York")


def is_regular_market_open(now_et: datetime) -> bool:
    if now_et.weekday() >= 5:
        return False

    market_open = time(9, 30)
    market_close = time(16, 0)
    return market_open <= now_et.time() < market_close


def get_session_mode(now_et: datetime) -> str:
    if is_regular_market_open(now_et):
        return "intraday"
    if now_et.weekday() >= 5:
        return "weekend_swing"
    return "after_hours_swing"


@st.cache_resource
def build_services() -> tuple[Settings, WatchlistService, ScanService]:
    settings = Settings.from_env()
    settings.validate()

    alpaca = AlpacaMarketDataClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        trading_base_url=settings.alpaca_base_url,
        data_base_url=settings.alpaca_data_url,
        data_feed=settings.alpaca_data_feed,
    )

    finnhub = FinnhubNewsClient(
        api_key=settings.finnhub_api_key,
        base_url=settings.finnhub_base_url,
    )

    watchlist_service = WatchlistService()
    scan_service = ScanService(
        alpaca=alpaca,
        finnhub=finnhub,
        catalyst_service=CatalystService(),
        sentiment_service=SentimentService(),
        signal_service=SignalService(),
        risk_service=RiskService(),
    )
    return settings, watchlist_service, scan_service


def main() -> None:
    st.set_page_config(page_title="Tradecore Alpha", layout="wide")

    settings, watchlist_service, scan_service = build_services()

    st.title("Tradecore Alpha")
    st.caption("Catalyst-driven trading decision engine")

    now_local = datetime.now()
    now_et = datetime.now(EASTERN_TZ)
    session_mode = get_session_mode(now_et)

    col1, col2, col3 = st.columns(3)
    col1.metric("Local Time", now_local.strftime("%Y-%m-%d %H:%M:%S"))
    col2.metric("ET Time", now_et.strftime("%Y-%m-%d %H:%M:%S"))
    col3.metric("Session Mode", session_mode)

    st.divider()

    with st.sidebar:
        st.header("Watchlists")

        existing_watchlists = watchlist_service.list_watchlists()

        if not existing_watchlists:
            default_watchlist = Watchlist(
                name="Default",
                items=[],
            )
            watchlist_service.save_watchlist(default_watchlist)
            existing_watchlists = watchlist_service.list_watchlists()

        selected_name = st.selectbox("Select watchlist", existing_watchlists)

        with st.expander("Create new watchlist"):
            new_name = st.text_input("New watchlist name")
            new_symbols = st.text_input("Symbols (comma separated)")
            if st.button("Create watchlist", use_container_width=True):
                symbols = [part.strip().upper() for part in new_symbols.split(",") if part.strip()]
                watchlist_service.create_watchlist(new_name, symbols)
                st.success(f"Created watchlist: {new_name}")
                st.rerun()

        with st.expander("Add symbol"):
            symbol = st.text_input("Symbol").upper().strip()
            thesis = st.text_input("Thesis")
            catalyst = st.text_input("Catalyst")
            note = st.text_area("Note")
            if st.button("Add symbol to watchlist", use_container_width=True):
                watchlist_service.add_symbol(
                    watchlist_name=selected_name,
                    symbol=symbol,
                    thesis=thesis,
                    catalyst=catalyst,
                    note=note,
                    manual_override=True,
                )
                st.success(f"Added {symbol} to {selected_name}")
                st.rerun()

    watchlist = watchlist_service.load_watchlist(selected_name)

    st.subheader(f"Watchlist: {watchlist.name}")

    if watchlist.items:
        watchlist_df = pd.DataFrame(
            [
                {
                    "Symbol": item.symbol,
                    "Source": item.source,
                    "Thesis": item.thesis,
                    "Catalyst": item.catalyst,
                    "Note": item.note,
                    "Priority": item.priority,
                }
                for item in watchlist.items
            ]
        )
        st.dataframe(watchlist_df, use_container_width=True, hide_index=True)
    else:
        st.info("This watchlist is empty.")

    st.divider()

    if st.button("Run scan", type="primary", use_container_width=True):
        with st.spinner("Running scan..."):
            rows = scan_service.run_watchlist_scan(
                watchlist=watchlist,
                intraday_timeframe=settings.intraday_timeframe,
                swing_timeframe=settings.swing_timeframe,
                session_mode=session_mode,
                catalyst_lookback_minutes=settings.catalyst_lookback_minutes,
                account_size=settings.account_size,
                risk_per_trade_pct=settings.risk_per_trade_pct,
                max_position_pct=settings.max_position_pct,
            )

        ready_rows = [row for row in rows if row.status == "ready"]
        watch_rows = [row for row in rows if row.status == "watch"]
        reject_rows = [row for row in rows if row.status == "reject"]
        no_data_rows = [row for row in rows if row.status in {"no_catalyst", "no_data"}]

        st.subheader("Ready Now")
        if ready_rows:
            st.dataframe(_rows_to_dataframe(ready_rows), use_container_width=True, hide_index=True)
        else:
            st.write("None")

        st.subheader("Watch For Tomorrow")
        if watch_rows:
            st.dataframe(_rows_to_dataframe(watch_rows), use_container_width=True, hide_index=True)
        else:
            st.write("None")

        st.subheader("Rejected / Incomplete")
        if reject_rows or no_data_rows:
            st.dataframe(_rows_to_dataframe(reject_rows + no_data_rows), use_container_width=True, hide_index=True)
        else:
            st.write("None")


def _rows_to_dataframe(rows: list) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": row.symbol,
                "Status": row.status.upper(),
                "Setup": row.setup.replace("_", " ").title(),
                "Score": row.score,
                "Trigger": row.trigger,
                "Entry": row.entry,
                "Stop": row.stop,
                "Target 1": row.target_1,
                "Target 2": row.target_2,
                "Shares": row.shares,
                "Catalyst": row.catalyst,
                "Timeframe": row.timeframe,
                "Confidence": row.confidence,
                "Note": row.note,
            }
            for row in rows
        ]
    )


if __name__ == "__main__":
    main()