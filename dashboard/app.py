import streamlit as st
import requests
import os

BACKEND_URL = os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')
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
TIMEOUT = 10

def fetch_price_data(ticker: str):
    r = requests.get(f"{BACKEND_URL}/prices/{ticker}", timeout=TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    d = r.json()
    return {"Date": d["dates"], "Adj Close": d["adj_close"]}

def search_portfolio(name: str):
    r = requests.get(f"{BACKEND_URL}/portfolios/{name}", timeout=TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()["holdings"]

def save_portfolio_to_backend(name: str, holdings: dict):
    is_new = search_portfolio(name)
    if is_new is None:
        r = requests.post(f"{BACKEND_URL}/portfolios",
                          json={"name": name, "holdings": holdings}, timeout=TIMEOUT)
    else:
        r = requests.put(f"{BACKEND_URL}/portfolios/{name}",
                         json={"holdings": holdings}, timeout=TIMEOUT)
    r.raise_for_status()        # raises on 4xx/5xx, which is what your docstring wants

def calculate_risk(measure: str, payload: dict):
    r = requests.post(f"{BACKEND_URL}/risk/{measure}", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["value"]


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