import streamlit as st

st.title("TradeCore Alpha")

symbol = st.text_input("Enter a stock symbol")

if st.button("Add symbol"):
    st.write("Added", symbol)