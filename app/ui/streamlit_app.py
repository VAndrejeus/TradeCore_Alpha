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
st.write(st.session_state.watchlist)