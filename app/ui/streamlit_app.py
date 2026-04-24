import pandas as pd
import streamlit as st

st.title("TradeCore Alpha")

if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

symbol = st.text_input("Enter a stock symbol")

if st.button("Add symbol"):
    clean_symbol = symbol.upper().strip()

    if clean_symbol and clean_symbol not in st.session_state.watchlist:
        st.session_state.watchlist.append(clean_symbol)

st.write("Current watchlist:")

watchlist_df = pd.DataFrame({"Symbol": st.session_state.watchlist, "Ticker": st.session_state.watchlist})

st.dataframe(watchlist_df, use_container_width=True, hide_index=True)