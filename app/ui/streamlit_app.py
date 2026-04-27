import json 
from pathlib import Path

import pandas as pd
import streamlit as st
import random

#load alpacamarket for symbol data
from app.clients.alpaca_market_data import AlpacaMarketDataClient
from app.config import Settings







WATCHLIST_FILE = Path("app/data/watchlist/default.json")
WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)

settings = Settings.from_env()

alpaca = AlpacaMarketDataClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
    trading_base_url=settings.alpaca_base_url,
    data_base_url=settings.alpaca_data_url,
    data_feed=settings.alpaca_data_feed,
)



st.title("TradeCore Alpha")

# check to see if watchlist file already exist and load it, or create empty watchlist
if "watchlist" not in st.session_state:
    if WATCHLIST_FILE.exists():
        st.session_state.watchlist =json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    else:
        st.session_state.watchlist = []

# initiate empty symbol key
if "symbol" not in st.session_state:
    st.session_state.symbol = ""

# funstion for the add symbol button to use
def add_symbol():
    clean_symbol = st.session_state.symbol.upper().strip()
    
    if not clean_symbol:
        st.session_state.message = "Please enter a symbol."
        st.session_state.message_type = "warning"
        return
    
    if clean_symbol in st.session_state.watchlist: # check for duplicate already existing in wactchilst 
        st.session_state.message = f"{clean_symbol} is already in the watchlist"
        st.session_state.message_type = "warning"
        st.session_state.symbol = ""
        return
    
    # if all is good, add symbol to the watchlist
    st.session_state.watchlist.append(clean_symbol)
    st.session_state.symbol = "" # clean input field after successfull watchlist addition
    st.session_state.message = f"{clean_symbol} added to the watchlist"
    st.session_state.message_type = "success"  

# remove symbol function to use with the remove button
def remove_selected_symbol():
    selected_symbol = st.session_state.remove_symbol
    if not selected_symbol:
        st.session_state.message = "Please select a symbol to remove"
        st.session_state.message_type = "warning"
        return
    if selected_symbol in st.session_state.watchlist:
        st.session_state.watchlist.remove(selected_symbol)
        st.session_state.message = f"{selected_symbol} was removed from the watchlist"
        st.session_state.message_type = "success"
        st.session_state.remove_symbol = "" # reset dropdown to empty

# color for the %change column function
def color_change(value):
    if value is None:
        return ""
    if value > 0:
        return "color: green"
    if value < 0:
        return "color: red"
    return ""

#formatter for the %change column function
def format_change(x):
    if x is None:
        return "N/A"
    return f"{x:+.2f}%"


# create columns to hold symbol input field and add button in a container
with st.container(border=True):
    add_col1, add_col2 = st.columns([1, 1])
    with add_col1:
        st.text_input("Enter a stock symbol", key="symbol") # store text field input inside session state
    with add_col2:
        st.write("")
        st.button( "Add symbol", on_click=add_symbol, # add symbol button with connecte fucnton ( callback on_click)
                  disabled=not st.session_state.symbol.strip()) #disabled if input is empty

st.divider()

#Create columns to hold remove dropbox and remove button in a container
with st.container(border=True):
    rem_col1, rem_col2 = st.columns([1, 1])
    with rem_col1:
        st.selectbox("Select a symbol to remove",
            options=[""] + st.session_state.watchlist, key="remove_symbol",
        )
    with rem_col2:
        #remove symbol button
        st.write("")
        st.button("Remove Symbol", on_click=remove_selected_symbol,
                  disabled=not st.session_state.remove_symbol) # disabled if nothing is selected

#columns for add to watchlist and refresh buttons   
watch_col1, watch_col2 = st.columns([1,1])
with watch_col1:
    if st.button("Save watchlist"):
        WATCHLIST_FILE.write_text(
            json.dumps(st.session_state.watchlist, indent=2),
            encoding="utf-8",
        )
        st.session_state.message = "Watchlist saved."
        st.session_state.message_type = "success"
with watch_col2:
    # refresh button for the watchlist
    if st.button("Refrsh"):
        st.session_state.message = "Watchlist refreshed"
        st.session_state.message_type = "success"
        st.rerun()
        

#Display warning and success messages logic, also remove messages after dsiplay
if "message" in st.session_state:
    if st.session_state.message_type == "success":
        st.success(st.session_state.message)
    elif st.session_state.message_type =="warning":
        st.warning(st.session_state.message)

    #delete messages
    del st.session_state.message
    del st.session_state.message_type

# loop that generates numbers from alpaca
prices = []
changes = []
for symbol in st.session_state.watchlist:
    bars = alpaca.get_bars(symbol, settings.swing_timeframe, limit=2)
    
    if len(bars) < 2:
        prices.append(None)
        changes.append(None)
        continue
    latest = bars[-1].close
    previous = bars[-2].close

    prices.append(latest)

    if previous == 0:
        changes.apeend(None)
    else:
        change = (latest - previous) / previous * 100
        changes.append(change)





with st.container(border=True):

    st.write("Current watchlist:")

    watchlist_df = pd.DataFrame({"Symbol": st.session_state.watchlist, "Price": prices, "% Change": changes})

    st.dataframe(watchlist_df.style.format( {"Price": "${:.2f}", "% Change": format_change}).applymap(color_change, subset=["% Change"]), use_container_width=True, hide_index=True)

with st.container(border=True):

    st.write("Current Catalyst Events:")

    signals_df = pd.DataFrame({"Symbol": st.session_state.watchlist,
                               "Status" : ["Test" for symbol in st.session_state.watchlist],
                               "Setup": ["Test_setup" for symbol in st.session_state.watchlist], 
                               "Score": [0 for symbol in st.session_state.watchlist],
                               "Trigger": ["Test trigger" for symbol in st.session_state.watchlist],
                               "Entry": [random.uniform(50, 200) for symbol in st.session_state.watchlist], 
                               "Stop": [random.uniform(50, 200) for symbol in st.session_state.watchlist], 
                               "Target 1": [random.uniform(5, 200) for symbol in st.session_state.watchlist], 
                               "Target 2": [random.uniform(50, 200) for symbol in st.session_state.watchlist] })
    
    st.dataframe(signals_df.style.format({"Entry": "${:.2f}", "Stop" : "${:.2f}", "Target 1": "${:.2f}", "Target 2": "${:.2f}"}),
                use_container_width=True)

                                          