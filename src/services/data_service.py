import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from src.models.historical_data import HistoricalData
from src.models.portfolio_header import PortfolioHeader
from src.models.portfolio_composition import PortfolioComposition
from src.schemas.schema import Portfolio

def sync_ticker(db: Session, ticker: str, lookback_days: int = 500)-> dict:
    """This function syncs the historical adjusted close price of the ticker with the databae
    Args:
        db:
        ticker:
        lookback_days: 
    Returns:
        Status of the synced ticker (dict)
    """

    # Appending .NS if not present as suffix and if .BO is present swap it with .NS
    ticker = ticker.strip().upper()
    if ticker.endswith(".BO"):
        ticker = ticker.removesuffix(".BO")
        ticker =  f"{ticker}.NS"
    elif not ticker.endswith(".NS"):
        ticker = f"{ticker}.NS"

    # Retrieve latest records for the ticker in the DB
    latest_record = db.execute(select(func.max(HistoricalData.date))
               .where(HistoricalData.ticker == ticker)).scalar()

    # today = datetime.utcnow().date()
    today = datetime.now(timezone.utc).date()

    # Set the start date according to the latest available record for the ticker
    if latest_record is None:
        start_date = today - timedelta(days=int(lookback_days * 1.5))
        is_incremental = False
    else:
        latest_date = latest_record.date() if isinstance(latest_record, datetime) else latest_record
        if latest_date >= today:
            return {"ticker": ticker, "status": "up-to-date","rows_inserted": 0}
        else:
            start_date = latest_date
            is_incremental = True

    end_date = today + timedelta(days=1)

    # Format dates as ISO strings
    start_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else str(start_date)
    end_str = end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else str(end_date)


    df = yf.download(
        ticker,
        start=start_str,
        end=end_str,
        progress=False,
        auto_adjust=False
    )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    price_col = "Adj Close" if "Adj Close" in df.columns else ("Close" if "Close" in df.columns else None)

    if price_col is None:
        raise ValueError(f"Neither 'Adj Close' nor 'Close' found in data columns: {list(df.columns)}")

    # Changing the column name to be consistant with thw database column name
    df = df[[price_col]].rename(columns={price_col: "Adj Close"}).copy()

    # Resetting "Date" to as column 
    df.reset_index(inplace=True)
    df["Date"] = pd.to_datetime(df["Date"]).dt.date

    df["log_return"] = np.log(df["Adj Close"]/df["Adj Close"].shift(1))

    if is_incremental:
        df = df[df["Date"] > start_date]

    df.dropna(subset=["Adj Close", "log_return"], inplace=True)

    if df.empty:
        return {"ticker": ticker, "status": "up-to-date","rows_inserted": 0}

    records_to_insert = [
        HistoricalData(
            date=row["Date"],
            ticker=ticker,
            adj_close=float(row["Adj Close"]),
            log_return=float(row["log_return"])
        ) for row in df.to_dict(orient="records")
    ]
    db.add_all(records_to_insert)
    db.commit()

    return {"ticker": ticker,
             "status": "synced",
             "rows_inserted": len(records_to_insert),
             "from_date": str(df["Date"].min()),
             "to_date": str(df["Date"].max())
    }

def get_ticker_price():
    
    pass

def get_portfolio_components(
        db: Session, 
        portfolio_name: str)-> Portfolio:

    portfolio = Portfolio()

    stmt = (select(PortfolioComposition.ticker, PortfolioComposition.units)
        .join(PortfolioHeader, PortfolioComposition.portfolio_id == PortfolioHeader.id)
        .where(PortfolioHeader.portfolio_name == portfolio_name)
    )
    result = db.execute(stmt).all()

    if not result:
        return None

    portfolio.name  = portfolio_name
    portfolio.holdings = {ticker: units for ticker, units in result}
    return portfolio

def check_portfolio_existance(
        db: Session,
        portfolio_name: str) -> bool:
    stmt = (select(PortfolioHeader.portfolio_name)
            .where(PortfolioHeader.portfolio_name == portfolio_name)
    )

    result = db.execute(stmt).scalar_one_or_none()

    if result is None:
        return False
        # raise HTTPException(status_code=404, detail="Portfolio not found")
    return True

        

def get_portfolio_returns(
    db: Session, 
    units: dict[str, float], 
    lookback_days: int = 500
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """
    Synchronizes historical market data, aligns multiple asset series by date,
    and computes dynamic daily portfolio valuations, weights, and returns.

    Args:
        db: Active SQLAlchemy database session.
        units: Dictionary mapping ticker symbols to share quantities held.
        lookback_days: Number of aligned historical trading sessions to retrieve.

    Returns:
        tuple containing:
            - returns_df: T x N individual asset log returns.
            - portfolio_returns: T x 1 exact daily portfolio log returns.
            - weights_df: T x N dynamic daily asset weights.
            - portfolio_value: T x 1 daily portfolio currency value.
    """
    if not units or any(q <= 0 for q in units.values()):
        raise ValueError("Portfolio units must be non-empty and strictly positive.")

    # 1. Normalize ticker keys and ensure data is synced in SQLite
    normalized_units = {}
    for ticker, qty in units.items():
        sym = ticker.strip().upper()
        if sym.endswith(".BO"):
            sym = sym.removesuffix(".BO") + ".NS"
        elif not sym.endswith(".NS"):
            sym = f"{sym}.NS"
        
        sync_ticker(db, sym, lookback_days=lookback_days)
        normalized_units[sym] = float(qty)

    tickers = list(normalized_units.keys())

    # 2. Query historical prices and log returns
    stmt = (
        select(HistoricalData.date, HistoricalData.ticker, HistoricalData.adj_close, HistoricalData.log_return)
        .where(HistoricalData.ticker.in_(tickers))
        .order_by(HistoricalData.date.asc())
    )
    records = db.execute(stmt).all()

    if not records:
        raise ValueError("No historical records found for the requested portfolio.")

    raw_df = pd.DataFrame(records, columns=["date", "ticker", "adj_close", "log_return"])

    # 3. Pivot tables: Rows = Date, Columns = Ticker
    prices_df = raw_df.pivot(index="date", columns="ticker", values="adj_close")
    returns_df = raw_df.pivot(index="date", columns="ticker", values="log_return")

    # 4. Align dates across all assets (drop non-overlapping dates/holidays)
    prices_df.dropna(inplace=True)
    returns_df = returns_df.loc[prices_df.index].dropna()

    # Re-slice prices to match valid return dates
    common_dates = prices_df.index.intersection(returns_df.index)
    prices_df = prices_df.loc[common_dates]
    returns_df = returns_df.loc[common_dates]

    if len(prices_df) < lookback_days:
        raise ValueError(
            f"Insufficient aligned trading history. Requested {lookback_days} days, "
            f"but only {len(prices_df)} common dates exist across all tickers."
        )

    # Tail to the exact lookback window
    prices_df = prices_df.tail(lookback_days)
    returns_df = returns_df.tail(lookback_days)

    # 5. Compute dynamic portfolio values and daily weights
    # Reorder units vector to match DataFrame column ordering exactly
    units_series = pd.Series([normalized_units[col] for col in prices_df.columns], index=prices_df.columns)

    # Daily dollar position in each asset: P_it * units_i
    asset_values_df = prices_df.multiply(units_series, axis=1)

    # Total portfolio value: V_t = sum(P_it * units_i)
    portfolio_value = asset_values_df.sum(axis=1)

    # Dynamic weights on each day: w_it = (units_i * P_it) / V_t
    weights_df = asset_values_df.divide(portfolio_value, axis=0)

    # Exact daily portfolio log returns: ln(V_t / V_{t-1})
    portfolio_returns = np.log(portfolio_value / portfolio_value.shift(1)).dropna()

    # Align matrices to drop the initial shift NaN
    aligned_idx = portfolio_returns.index
    returns_df = returns_df.loc[aligned_idx]
    weights_df = weights_df.loc[aligned_idx]
    portfolio_value = portfolio_value.loc[aligned_idx]

    return returns_df, portfolio_returns, weights_df, portfolio_value