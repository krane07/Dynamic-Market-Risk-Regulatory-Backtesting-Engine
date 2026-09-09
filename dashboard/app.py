import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 1. Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Stock & Portfolio Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Financial Data Dashboard")

# Initialize Session State for Portfolio Tickers
if "portfolio" not in st.session_state:
    st.session_state.portfolio = ["AAPL", "MSFT", "GOOGL"]

# -----------------------------------------------------------------------------
# 2. Sidebar Options
# -----------------------------------------------------------------------------
st.sidebar.header("Dashboard Settings")

# Mode Selection: Single Stock vs. Portfolio
mode = st.sidebar.radio(
    "Select Mode:",
    ["Single Stock / Index", "Build Portfolio"]
)  

# Date Range Picker
st.sidebar.subheader("Select Date Range")
start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("End Date", datetime.now())

# -----------------------------------------------------------------------------
# 3. Mode 1: Single Stock / Index
# -----------------------------------------------------------------------------
if mode == "Single Stock / Index":
    stock_exchange = st.sidebar.radio(
    "Select Market:",
    ["NSE","BSE"]
    ) 
    st.header("🔍 Single Stock / Index Analysis")
    
    ticker_input = st.text_input(
        "Enter Ticker Symbol (e.g., AAPL, TSLA, ^GSPC for S&P 500, ^NSEI for Nifty 50):", 
        value="AAPL"
    ).upper().strip()


    if ticker_input:
        with st.spinner(f"Fetching data for {ticker_input}..."):
            data = yf.download(ticker_input, start=start_date, end=end_date)
            
            if not data.empty:
                # Extract Open and Close prices
                open_close_df = data[['Open', 'Close']].copy()
                
                # Metrics Summary
                latest_close = open_close_df['Close'].iloc[-1] if not open_close_df.empty else 0
                latest_open = open_close_df['Open'].iloc[-1] if not open_close_df.empty else 0
                # st.write(latest_close.dtype)
                col1, col2 = st.columns(2)
                col1.metric("Latest Open Price", f"{float(latest_open.iloc[0]):,.2f}")
                col2.metric("Latest Close Price", f"{float(latest_close.iloc[0]):,.2f}")

                # Display Visualizations
                st.subheader("Price Trends (Open vs Close)")
                st.write(open_close_df)
                st.line_chart(open_close_df)

                # Display Day-Wise Data Table
                st.subheader("Day-Wise Opening & Closing Data")
                st.dataframe(open_close_df.sort_index(ascending=False), use_container_width=True)
            else:
                st.error(f"No data found for ticker '{ticker_input}'. Please check the symbol and try again.")

# -----------------------------------------------------------------------------
# 4. Mode 2: Portfolio Builder
# -----------------------------------------------------------------------------
elif mode == "Build Portfolio":
    st.header("💼 Portfolio Manager")
    
    # Section to Add New Ticker
    col_input, col_button = st.columns([3, 1])
    with col_input:
        new_ticker = st.text_input("Search / Enter Ticker Symbol to Add:").upper().strip()
    with col_button:
        st.write("") # Spacing alignment
        st.write("")
        if st.button("Add to Portfolio"):
            if new_ticker:
                if new_ticker not in st.session_state.portfolio:
                    st.session_state.portfolio.append(new_ticker)
                    st.success(f"Added {new_ticker} to portfolio!")
                else:
                    st.warning(f"{new_ticker} is already in your portfolio.")

    # Section to Manage Existing Tickers
    st.subheader("Manage Portfolio Tickers")
    st.session_state.portfolio = st.multiselect(
        "Modify your selection (remove items by clicking 'x'):",
        options=st.session_state.portfolio,
        default=st.session_state.portfolio
    )

    # Fetch and Display Portfolio Data
    if st.session_state.portfolio:
        with st.spinner("Fetching portfolio data..."):
            portfolio_data = yf.download(st.session_state.portfolio, start=start_date, end=end_date)
            
            if not portfolio_data.empty:
                st.subheader("Closing Price Comparison")
                close_df = portfolio_data['Close']
                st.line_chart(close_df)

                st.subheader("Day-Wise Opening Data")
                st.dataframe(portfolio_data['Open'].sort_index(ascending=False), use_container_width=True)

                st.subheader("Day-Wise Closing Data")
                st.dataframe(portfolio_data['Close'].sort_index(ascending=False), use_container_width=True)
            else:
                st.error("Unable to retrieve data for the selected tickers.")
    else:
        st.info("Your portfolio is currently empty. Add ticker symbols using the input box above.")