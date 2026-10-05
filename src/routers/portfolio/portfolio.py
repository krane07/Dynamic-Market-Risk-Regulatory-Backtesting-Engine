from datetime import date
from typing import Literal
from fastapi import HTTPException, APIRouter, Depends
from sqlalchemy.orm import Session

from src.schemas.schema import Portfolio, HoldingsBody, RiskRequest
from src.core.database import get_db
from src.services.data_service import get_ticker_price, get_portfolio_components, check_portfolio_existance

router = APIRouter(tags=["portfolio"])

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
    db_save_portfolio(p.name, p.holdings)
    return p

@router.put("/modify{name}")
def replace_portfolio(name: str,
                      body: HoldingsBody,
                      db: Session = Depends(get_db)):
    if not check_portfolio_existance(db, name):
        raise HTTPException(404, "Portfolio not found")
    db_save_portfolio(name, body.holdings)
    return {"name": name, "holdings": body.holdings}

@router.delete("/{name}",status_code=204)
def delete_portfolio(name: str,
                     db: Session = Depends(get_db)):
    db_delete_portfolio(name)