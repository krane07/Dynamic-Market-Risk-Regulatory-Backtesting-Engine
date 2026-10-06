from datetime import date
from typing import Literal
from fastapi import HTTPException, APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.schemas.schema import Portfolio, HoldingsBody
from src.core.database import get_db
from src.services.data_service import (check_ticker_existance,
                                       TickerLookupError,
                                       get_portfolio_components,
                                       check_portfolio_existance,
                                       db_save_portfolio,
                                       db_delete_portfolio)

router = APIRouter(tags=["portfolio"])

@router.get("/ticker/{ticker}")
def search_ticker(ticker: str):
    try:
        exists = check_ticker_existance(ticker)
    except TickerLookupError:
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify ticker right now. Try again later.",
        )

    if not exists:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail=f"Ticker '{ticker.strip().upper()}' not found",
        )

    return {"ticker": ticker.strip().upper(), "exists": "Ticker found"}


@router.get("/{name}")
def get_portfolio(name: str,
                  include_components: bool,
                  db: Session = Depends(get_db)):
    if include_components:
        p = get_portfolio_components(db,name)
        if p is None:
            raise HTTPException(404, "Portfolio not found")
        return p
    return check_portfolio_existance(db, name)
    

@router.post("/save", status_code=201)
def create_portfolio(p: Portfolio,
                    db: Session = Depends(get_db)):
    if check_portfolio_existance(db, p.name):
        raise HTTPException(409, "Portfolio already exists")
    
    return db_save_portfolio(db, p)

@router.put("/modify{name}", status_code=200)
def replace_portfolio(name: str,
                      body: HoldingsBody,
                      db: Session = Depends(get_db)):
    if not check_portfolio_existance(db, name):
        raise HTTPException(404, "Portfolio not found")
    portfolio = Portfolio()
    portfolio.name = name
    portfolio.holdings = body.holdings
    
    return db_save_portfolio(db, portfolio)

@router.delete("/{name}",status_code=204)
def delete_portfolio(name: str,
                     db: Session = Depends(get_db)):
    db_delete_portfolio(db, name)