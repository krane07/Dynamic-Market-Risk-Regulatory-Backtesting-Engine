from datetime import date
from typing import Literal
from fastapi import APIRouter, HTTPException

from src.schemas.schema import Portfolio, HoldingsBody, RiskRequest
from src.core.database import SessionLocal
from src.services.data_service import get_ticker_price, get_portfolio_components, check_portfolio_existance

router = APIRouter(prefix="prices", tags=["prices"])


@router.get("/prices/{ticker}")
def get_prices(ticker: str, start: date | None = None, end: date | None = None):
    db = SessionLocal()
    df = db_get_prices(ticker)          # your DB query
    if df is None or df.empty:
        raise HTTPException(404, f"No data for {ticker}")
    return {"dates": df["Date"].dt.strftime("%Y-%m-%d").tolist(),
            "adj_close": df["Adj Close"].tolist()}