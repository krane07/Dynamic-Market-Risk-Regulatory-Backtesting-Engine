import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from src.models.historical_data import HistoricalData

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