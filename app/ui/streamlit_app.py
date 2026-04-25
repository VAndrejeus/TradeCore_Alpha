import json 
from pathlib import Path

import pandas as pd
import streamlit as st

WATCHLIST_FILE = Path("app/data/watchlist/default.json")
WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)

st.title("TradeCore Alpha")

if "watchlist" not in st.session_state:
    if WATCHLIST_FILE.exists():
        st.session_state.watchlist =json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    else:
        st.session_state.watchlist = []

symbol = st.text_input("Enter a stock symbol")

if st.button("Add symbol"):
    clean_symbol = symbol.upper().strip()

    if clean_symbol and clean_symbol not in st.session_state.watchlist:
        st.session_state.watchlist.append(clean_symbol)

remove_symbol = st.selectbox(
    "Select a symbol to remove",
    options=[""] + st.session_state.watchlist,
)

if st.button("Remove Symbol"):
    if remove_symbol in st.session_state.watchlist:
        st.session_state.watchlist.remove(remove_symbol)

if st.button("Save watchlist"):
    WATCHLIST_FILE.write_text(
        json.dumps(st.session_state.watchlist, indent=2),
        encoding="utf-8",
    )
    st.success("Watchlist saved.")

st.write("Current watchlist:")

watchlist_df = pd.DataFrame({"Symbol": st.session_state.watchlist})

st.dataframe(watchlist_df, use_container_width=True, hide_index=True)