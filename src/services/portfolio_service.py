import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.historical_data import HistoricalData
from src.services.data_service import sync_ticker


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