import streamlit as st

# -----------------------------------------------------------------------------
# 1. Page configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Stock & Portfolio Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Financial Data Dashboard")

RISK_MEASURES = ["VaR", "Expected Shortfall"]

# -----------------------------------------------------------------------------
# 2. Session state defaults (initialised once)
# -----------------------------------------------------------------------------
DEFAULTS = {
    "portfolio_tickers": {},        # holdings being built in "create" mode
    "portfolio_mode": None,         # None | "create" | "search"
    "current_portfolio_name": "",   # name of the portfolio being created
    "loaded_portfolio": None,       # holdings of the portfolio found by "search"
    "loaded_portfolio_name": "",
    "editing": False,               # edit mode for a searched portfolio
}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)


# -----------------------------------------------------------------------------
# 3. Backend placeholders (replace the bodies with your endpoint calls)
# -----------------------------------------------------------------------------
def fetch_price_data(ticker: str):
    """Call endpoint to fetch data from the database. Return None if not found."""
    return {
        "Date": ["25-09-2026", "26-09-2026", "27-09-2026", "28-09-2026"],
        "Adj Close": [12, 13, 12, 16],
    }


def search_portfolio(name: str):
    """Call endpoint to search the portfolio. Return {ticker: qty} or None."""
    return {"AAPL": 3, "INFY": 5, "TCS": 8}


def save_portfolio_to_backend(name: str, holdings: dict):
    """Call endpoint to save the portfolio. Raise an exception on failure."""
    pass


def calculate_risk(measure: str, payload):
    """Call the endpoint for VaR / Expected Shortfall."""
    return None


# -----------------------------------------------------------------------------
# 4. Reusable pieces
# -----------------------------------------------------------------------------
def risk_calculator(key: str, payload):
    """Dropdown + Calculate button. The result is kept in session state so it
    survives reruns (a plain `if st.button(...)` block disappears on the next
    interaction)."""
    col_measure, col_btn = st.columns([3, 1])

    with col_measure:
        measure = st.selectbox(
            "Risk measure",
            RISK_MEASURES,
            key=f"{key}_measure",
            label_visibility="collapsed",
        )
    with col_btn:
        clicked = st.button("Calculate", key=f"{key}_btn", width="stretch")

    if clicked:
        with st.spinner(f"Calculating {measure}..."):
            result = calculate_risk(measure, payload)
        st.session_state[f"{key}_result"] = (measure, result)

    saved = st.session_state.get(f"{key}_result")
    if saved:
        st.write(f"**{saved[0]}:** {saved[1]}")


def reset_edit_state():
    """Leave edit mode and discard any in-progress widget values."""
    for k in [k for k in st.session_state if k.startswith("qty_")]:
        del st.session_state[k]
    st.session_state.editing = False
    st.session_state.pop("draft", None)


# ---- callbacks for the "modify searched portfolio" flow ----
def start_edit():
    st.session_state.editing = True
    st.session_state.draft = dict(st.session_state.loaded_portfolio)


def cancel_edit():
    reset_edit_state()


def remove_ticker(ticker: str):
    st.session_state.draft.pop(ticker, None)
    st.session_state.pop(f"qty_{ticker}", None)


def save_edit():
    # Read the live widget values: callbacks run before the script reruns, so
    # `draft` may not have the latest number_input values yet.
    final = {
        t: int(st.session_state.get(f"qty_{t}", q))
        for t, q in st.session_state.draft.items()
    }
    final = {t: q for t, q in final.items() if q > 0}  # drop zero-quantity rows

    try:
        save_portfolio_to_backend(st.session_state.loaded_portfolio_name, final)
    except Exception as e:
        st.toast(f"Could not save portfolio: {e}", icon="❌")
        return  # stay in edit mode so nothing is lost

    st.session_state.loaded_portfolio = final
    reset_edit_state()
    st.toast("Portfolio saved", icon="✅")


# -----------------------------------------------------------------------------
# 5. Sidebar
# -----------------------------------------------------------------------------
st.sidebar.header("Dashboard Settings")

mode = st.sidebar.radio(
    "Select Mode:",
    ["Single Stock / Index", "Build Portfolio"],
)

# -----------------------------------------------------------------------------
# 6. Mode 1: Single Stock / Index
# -----------------------------------------------------------------------------
if mode == "Single Stock / Index":
    # stock_exchange = st.sidebar.radio("Select Market:", ["NSE", "BSE"])

    st.header("🔍 Single Stock / Index Analysis")

    ticker_input = st.text_input(
        "Enter Ticker Symbol (e.g., AAPL, TSLA, ^GSPC for S&P 500, ^NSEI for Nifty 50):",
        value="AAPL",
    ).upper().strip()

    if ticker_input:
        with st.spinner(f"Fetching data for {ticker_input}..."):
            data = fetch_price_data(ticker_input)

        if data:
            st.dataframe(data)
            risk_calculator("single", {"ticker": ticker_input, "data": data})
        else:
            st.warning(f"No data found for {ticker_input}.")

# -----------------------------------------------------------------------------
# 7. Mode 2: Portfolio Manager
# -----------------------------------------------------------------------------
elif mode == "Build Portfolio":
    st.header("💼 Portfolio Manager")

    # ------------------------------------------------------------------
    # Portfolio name + Search / Create
    # ------------------------------------------------------------------
    col_input, col_search, col_create = st.columns([3, 1, 1])

    with col_input:
        portfolio_name = st.text_input(
            "Portfolio Name",
            placeholder="Enter portfolio name",
        ).strip()

    with col_search:
        st.write("")  # alignment
        st.write("")
        search_clicked = st.button("Search", width="stretch")

    with col_create:
        st.write("")
        st.write("")
        create_clicked = st.button("+ Create", width="stretch")

    if search_clicked:
        if not portfolio_name:
            st.error("Please enter a portfolio name.")
        else:
            reset_edit_state()
            found = search_portfolio(portfolio_name)
            if found is None:
                st.session_state.portfolio_mode = None
                st.session_state.loaded_portfolio = None
                st.warning(f"No portfolio named '{portfolio_name}' was found.")
            else:
                st.session_state.portfolio_mode = "search"
                st.session_state.loaded_portfolio = found
                st.session_state.loaded_portfolio_name = portfolio_name

    if create_clicked:
        if not portfolio_name:
            st.error("Please enter a portfolio name.")
        else:
            reset_edit_state()
            # Start with a clean slate unless we're continuing the same draft
            if (
                st.session_state.portfolio_mode != "create"
                or st.session_state.current_portfolio_name != portfolio_name
            ):
                st.session_state.portfolio_tickers = {}
            st.session_state.portfolio_mode = "create"
            st.session_state.current_portfolio_name = portfolio_name

    # ------------------------------------------------------------------
    # Create portfolio
    # ------------------------------------------------------------------
    if st.session_state.portfolio_mode == "create":
        st.divider()
        st.subheader(f"Create Portfolio: {st.session_state.current_portfolio_name}")

        col_ticker, col_qty, col_add = st.columns([2, 1, 1])

        with col_ticker:
            ticker = st.text_input(
                "Add Stock",
                placeholder="Enter ticker, e.g. AAPL",
                key="ticker_input",
            ).upper().strip()

        with col_qty:
            quantity = st.number_input("Enter Quantity", min_value=1, step=1)

        with col_add:
            st.write("")
            st.write("")
            if st.button("Add", width="stretch"):
                if not ticker:
                    st.error("Please enter a ticker.")
                elif ticker in st.session_state.portfolio_tickers:
                    st.warning(f"{ticker} has already been added.")
                else:
                    # TODO: check that the ticker exists
                    st.session_state.portfolio_tickers[ticker] = quantity
                    st.rerun()

        if st.session_state.portfolio_tickers:
            st.write("### Stocks in Portfolio")

            col_h1, col_h2, _ = st.columns([3, 1, 1])
            col_h1.write("*Ticker*")
            col_h2.write("*Quantity*")

            for t, qty in list(st.session_state.portfolio_tickers.items()):
                col_stock, col_quant, col_remove = st.columns([3, 1, 1])
                col_stock.write(f"**{t}**")
                col_quant.write(f"**{qty}**")
                with col_remove:
                    if st.button("Remove", key=f"remove_{t}", width="stretch"):
                        del st.session_state.portfolio_tickers[t]
                        st.rerun()

            st.divider()
            col_save, col_risk = st.columns([1, 2])

            with col_save:
                if st.button("💾 Save Portfolio", width="stretch"):
                    name = st.session_state.current_portfolio_name
                    holdings = dict(st.session_state.portfolio_tickers)
                    try:
                        save_portfolio_to_backend(name, holdings)
                        st.success(
                            f"Portfolio '{name}' saved successfully "
                            f"with {len(holdings)} stock(s)."
                        )
                    except Exception as e:
                        st.error(f"Could not save portfolio: {e}")

            # with col_risk:
            #     risk_calculator("create", st.session_state.portfolio_tickers)
        else:
            st.info("No stocks added yet.")

    # ------------------------------------------------------------------
    # Search result: view / modify portfolio
    # ------------------------------------------------------------------
    elif (
        st.session_state.portfolio_mode == "search"
        and st.session_state.loaded_portfolio is not None
    ):
        st.divider()
        st.subheader(f"Portfolio: {st.session_state.loaded_portfolio_name}")

        if not st.session_state.editing:
            # View mode: holdings first, then the Modify button
            for t, qty in st.session_state.loaded_portfolio.items():
                col_stock, col_quant = st.columns([3, 1])
                col_stock.write(f"**{t}**")
                col_quant.write(int(qty))

            st.button("Modify", width="stretch", on_click=start_edit)

        else:
            # Edit mode: Modify button is gone, editing controls are shown
            draft = st.session_state.draft

            for t in list(draft):
                col_stock, col_quant, col_remove = st.columns([3, 2, 1])

                col_stock.write(f"**{t}**")
                with col_quant:
                    draft[t] = st.number_input(
                        label=f"Quantity for {t}",
                        min_value=0,
                        value=int(draft[t]),
                        step=1,
                        label_visibility="collapsed",
                        key=f"qty_{t}",
                    )
                with col_remove:
                    st.button(
                        "🗑️",
                        key=f"rm_{t}",
                        help=f"Remove {t}",
                        on_click=remove_ticker,
                        args=(t,),
                    )

            if not draft:
                st.info("No holdings left. Saving will give you an empty portfolio.")

            col_cancel, col_save = st.columns(2)
            col_cancel.button("Cancel", width="stretch", on_click=cancel_edit)
            col_save.button(
                "Save portfolio",
                type="primary",
                width="stretch",
                on_click=save_edit,
            )





















#################################################################################################################

# import streamlit as st
# import yfinance as yf
# import pandas as pd
# from datetime import datetime, timedelta
# import requests

# # -----------------------------------------------------------------------------
# # 1. Page Configuration
# # -----------------------------------------------------------------------------
# st.set_page_config(
#     page_title="Stock & Portfolio Dashboard",
#     page_icon="📈",
#     layout="wide"
# )

# st.title("📈 Financial Data Dashboard")

# # Initialize Session State for Portfolio Tickers        
# if "portfolio" not in st.session_state:
#     st.session_state.portfolio = ["AAPL", "MSFT", "GOOGL"]

# # -----------------------------------------------------------------------------
# # 2. Sidebar Options
# # -----------------------------------------------------------------------------
# st.sidebar.header("Dashboard Settings")

# # Mode Selection: Single Stock vs. Portfolio
# mode = st.sidebar.radio(
#     "Select Mode:",
#     ["Single Stock / Index", "Build Portfolio"]
# )  
# # -----------------------------------------------------------------------------
# # 3. Mode 1: Single Stock / Index
# # -----------------------------------------------------------------------------
# if mode == "Single Stock / Index":
#     stock_exchange = st.sidebar.radio(
#     "Select Market:",
#     ["NSE","BSE"]
#     ) 
#     st.header("🔍 Single Stock / Index Analysis")
    
#     ticker_input = st.text_input(
#         "Enter Ticker Symbol (e.g., AAPL, TSLA, ^GSPC for S&P 500, ^NSEI for Nifty 50):", 
#         value="AAPL"
#     ).upper().strip()


#     if ticker_input:
#         with st.spinner(f"Fetching data for {ticker_input}..."):
#            # Call Endpoint to fetch data from database

#            dummy_data = {"Date":["25-09-2026","26-09-2026","27-09-2026","28-09-2026"],
#                          "Adj Close": [12,13,12,16]}

#            if dummy_data:
#                print("Data not found")
#                Cal_risk = st.menu_button("Calculate", options=["VaR", "Expected Shortfall"])
#                if Cal_risk == "VaR":
#                 st.write("Calculating VaR")
               
#                     # call Endpoint that calculates Value at Risk
               
#                elif Cal_risk == "Expected Shortfall":
#                 st.write("Calculating Expected Shortfall")
               
#                     # call Endpoint that calculates Expected Shortfall

#            else:
#                print("Data not found")

# # -----------------------------------------------------------------------------
# # 4. Mode 2: Portfolio Builder
# # -----------------------------------------------------------------------------
# elif mode == "Build Portfolio":
#     st.header("💼 Portfolio Manager")

#     # Initialize session state
#     if "portfolio_tickers" not in st.session_state:
#         st.session_state.portfolio_tickers = {}

#     if "portfolio_mode" not in st.session_state:
#         st.session_state.portfolio_mode = None

#     # --------------------------------------------------
#     # Portfolio Name + Search/Create
#     # --------------------------------------------------
#     col_input, col_search, col_create = st.columns([3, 1, 1])

#     with col_input:
#         portfolio_name = st.text_input(
#             "Portfolio Name",
#             placeholder="Enter portfolio name"
#         ).strip()

#     with col_search:
#         st.write("")  # Alignment
#         st.write("")
#         if st.button("Search", use_container_width=True):

#             if not portfolio_name:
#                 st.error("Please enter a portfolio name.")

#             else:
#                 st.session_state.portfolio_mode = "search"
#                 st.session_state.portfolio_to_be_searched = portfolio_name
#                 # Search functionality will be added later
#                 # st.info(f"Searching for portfolio: {portfolio_name}")

#     with col_create:
#         st.write("")  # Alignment
#         st.write("")
#         if st.button("+ Create", use_container_width=True):

#             if not portfolio_name:
#                 st.error("Please enter a portfolio name.")

#             else:
#                 st.session_state.portfolio_mode = "create"
#                 st.session_state.current_portfolio_name = portfolio_name

#     # --------------------------------------------------
#     # Create Portfolio Section
#     # --------------------------------------------------
#     if st.session_state.portfolio_mode == "create":

#         st.divider()

#         st.subheader(
#             f"Create Portfolio: {st.session_state.current_portfolio_name}"
#         )

#         # Ticker input
#         col_ticker, col_qty, col_add = st.columns([2, 1, 1])

#         with col_ticker:
#             ticker = st.text_input(
#                 "Add Stock",
#                 placeholder="Enter ticker, e.g. AAPL",
#                 key="ticker_input"
#             ).upper().strip()

#         with col_qty:
#             quantity = st.number_input(
#                 label = "Enter Quantity",
#                 min_value=1,
#                 step=1
#             )

#         with col_add:
#             st.write("")
#             st.write("")
#             if st.button("Add", use_container_width=True):

#                 if not ticker:
#                     st.error("Please enter a ticker.")

#                 elif ticker in st.session_state.portfolio_tickers:
#                     st.warning(f"{ticker} has already been added.")

#                 else:
#                     # Functionality to check if the ticker exists
#                     #
#                     #
#                     # st.session_state.portfolio_tickers.append(ticker)
#                     st.session_state.portfolio_tickers[ticker] = quantity
#                     st.rerun()

#         # --------------------------------------------------
#         # Display Added Stocks
#         # --------------------------------------------------
#         if st.session_state.portfolio_tickers:

#             st.write("### Stocks in Portfolio")
#             col_stock_name, col_quant_stock, _= st.columns([3, 1, 1])
#             with col_stock_name:
#                 st.write(f"*Ticker*")
#             with col_quant_stock:
#                 st.write(f"*Quantity*")

#             for ticker, qty in st.session_state.portfolio_tickers.items():

#                 col_stock, col_quant, col_remove = st.columns([3, 1, 1])

#                 with col_stock:
#                     st.write(f"**{ticker}**")
#                 with col_quant:
#                     st.write(f"**{qty}**")

#                 with col_remove:
#                     if st.button(
#                         "Remove",
#                         key=f"remove_{ticker}",
#                         use_container_width=True
#                     ):
#                         del st.session_state.portfolio_tickers[ticker]
#                         st.rerun()
#             # --------------------------------------------------
#             # Save Portfolio
#             # --------------------------------------------------
#             st.divider()
#             col_save, col_cal_risk = st.columns([1, 1])
#             with col_save:
#                 if st.button("💾 Save Portfolio", use_container_width=True):

#                     portfolio_name = st.session_state.current_portfolio_name
#                     tickers = st.session_state.portfolio_tickers

#                     # Call Endpoint to save created portfolio

#                     st.success(
#                         f"Portfolio '{portfolio_name}' saved successfully "
#                         f"with {len(tickers)} stock(s)."
#                     )
#             with col_cal_risk:
#                 if st.button("Calculate ", use_container_width=True):
#                     Cal_risk = st.menu_button("Calculate", options=["VaR", "Expected Shortfall"])
#                     if Cal_risk == "VaR":
#                         st.write("Calculating VaR")

#                         # call Endpoint that calculates Value at Risk

#                     elif Cal_risk == "Expected Shortfall":
#                         st.write("Calculating Expected Shortfall")

#                         # call Endpoint that calculates Expected Shortfall

#         else:
#             st.info("No stocks added yet.")

#     if st.session_state.portfolio_mode == "search":
#         # Call Endpoint to search the Portfolio 
#         # if portfolio found display the components
#         ########################################

#         components = {"APPL": 3, "INFY": 5, "TCS": 8}
#         # ---------- callbacks ----------
#         def start_edit(components: dict):
#             st.session_state.editing = True
#             st.session_state.draft = dict(components)  # working copy, original untouched


#         def clear_widget_state():
#             for k in [k for k in st.session_state if k.startswith("qty_")]:
#                 del st.session_state[k]


#         def cancel_edit():
#             clear_widget_state()
#             st.session_state.editing = False
#             st.session_state.pop("draft", None)


#         def remove_ticker(ticker: str):
#             st.session_state.draft.pop(ticker, None)
#             st.session_state.pop(f"qty_{ticker}", None)


#         def save_edit():
#             # Read the live widget values (callbacks run before the script reruns,
#             # so the draft dict may not have the latest number_input values yet)
#             final = {
#                 t: int(st.session_state.get(f"qty_{t}", q))
#                 for t, q in st.session_state.draft.items()
#             }
#             final = {t: q for t, q in final.items() if q > 0}  # drop zero-quantity rows

#             save_portfolio(final)  # <-- your own persistence logic (DB / file / API)

#             clear_widget_state()
#             st.session_state.editing = False
#             st.session_state.pop("draft", None)
#             st.toast("Portfolio saved")


#         def save_portfolio(new_components: dict):
#             """Replace with your real save logic."""
#             raise NotImplementedError


#         # ---------- UI ----------
#         # `components` = your current saved portfolio, e.g. {"AAPL": 10, "MSFT": 5}
#         if not st.session_state.get("editing", False):
#             # View mode: show the components first (replace with your existing display code)
#             for ticker, qty in components.items():
#                 col_stock, col_quant = st.columns([3, 1])
#                 with col_stock:
#                     st.write(f"**{ticker}**")
#                 with col_quant:
#                     st.write(int(qty))

#             # ...then the Modify button underneath
#             st.button(
#                 "Modify",
#                 use_container_width=True,
#                 on_click=start_edit,
#                 args=(components,),
#             )
#         else:
#             # Edit mode: Modify button is gone, editing controls are shown
#             draft = st.session_state.draft

#             for ticker in list(draft):
#                 col_stock, col_quant, col_remove = st.columns([3, 2, 1])

#                 with col_stock:
#                     st.write(f"**{ticker}**")

#                 with col_quant:
#                     draft[ticker] = st.number_input(
#                         label=f"Quantity for {ticker}",
#                         min_value=0,
#                         value=int(draft[ticker]),
#                         step=1,
#                         label_visibility="collapsed",
#                         key=f"qty_{ticker}",
#                     )

#                 with col_remove:
#                     st.button(
#                         "🗑️",
#                         key=f"rm_{ticker}",
#                         help=f"Remove {ticker}",
#                         on_click=remove_ticker,
#                         args=(ticker,),
#                     )

#             if not draft:
#                 st.info("No holdings left. Saving will give you an empty portfolio.")

#             col_cancel, col_save = st.columns(2)
#             with col_cancel:
#                 st.button("Cancel", use_container_width=True, on_click=cancel_edit)
#             with col_save:
#                 st.button(
#                     "Save portfolio",
#                     type="primary",
#                     use_container_width=True,
#                     on_click=save_edit,
#                 )






#         # ########################################
#         # components = {"APPL": 3, "INFY": 5, "TCS": 8}
#         # if components:
#         #     for ticker, qty in components.items():
#         #         col_stock, col_quant= st.columns([3, 1])

#         #         with col_stock:
#         #             st.write(f"**{ticker}**")
#         #         with col_quant:
#         #             st.write(f"**{qty}**")

#         #     if st.button("Modify", use_container_width=True):
#         #         for ticker, qty in components.items():
#         #             col_stock, col_quant= st.columns([3, 1])
                
#         #             with col_stock:
#         #                 st.write(f"**{ticker}**")
#         #             with col_quant:
#         #                 new_qty = st.number_input(
#         #                             label=f"Quantity for {ticker}", # Unique label for accessibility
#         #                             min_value=0,                    # Keeps quantity from going negative
#         #                             value=int(qty),                 # The current quantity
#         #                             step=1,                         # Increases/decreases by 1
#         #                             label_visibility="collapsed",   # Hides the label to keep the UI clean
#         #                             key=f"qty_{ticker}"             # Unique key for Streamlit state tracking
#         #                 )
        
#         #                 # Update your dictionary if the user changes the value
#         #                 if new_qty != qty:
#         #                     components[ticker] = new_qty







# # elif mode == "Build Portfolio":
# #     st.header("💼 Portfolio Manager")
    
# #     # Section to Add New Ticker
# #     col_input, col_button = st.columns([3, 1])
# #     with col_input:
# #         new_ticker = st.text_input("Search / Enter Ticker Symbol to Add:").upper().strip()
# #     with col_button:
# #         st.write("") # Spacing alignment
# #         st.write("")
# #         if st.button("Add to Portfolio"):
# #             if new_ticker:
# #                 if new_ticker not in st.session_state.portfolio:
# #                     st.session_state.portfolio.append(new_ticker)
# #                     st.success(f"Added {new_ticker} to portfolio!")
# #                 else:
# #                     st.warning(f"{new_ticker} is already in your portfolio.")

# #     # Section to Manage Existing Tickers
# #     st.subheader("Manage Portfolio Tickers")
# #     st.session_state.portfolio = st.multiselect(
# #         "Modify your selection (remove items by clicking 'x'):",
# #         options=st.session_state.portfolio,
# #         default=st.session_state.portfolio
# #     )

# #     # Fetch and Display Portfolio Data
# #     if st.session_state.portfolio:
# #         with st.spinner("Fetching portfolio data..."):
# #             portfolio_data = yf.download(st.session_state.portfolio, start=start_date, end=end_date)
            
# #             if not portfolio_data.empty:
# #                 st.subheader("Closing Price Comparison")
# #                 close_df = portfolio_data['Close']
# #                 st.line_chart(close_df)

# #                 st.subheader("Day-Wise Opening Data")
# #                 st.dataframe(portfolio_data['Open'].sort_index(ascending=False), use_container_width=True)

# #                 st.subheader("Day-Wise Closing Data")
# #                 st.dataframe(portfolio_data['Close'].sort_index(ascending=False), use_container_width=True)
# #             else:
# #                 st.error("Unable to retrieve data for the selected tickers.")
# #     else:
# #         st.info("Your portfolio is currently empty. Add ticker symbols using the input box above.")