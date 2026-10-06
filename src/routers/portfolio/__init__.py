from fastapi import APIRouter
from src.routers.portfolio import portfolio, risk

portfolio_router = APIRouter(prefix="/portfolio")

portfolio_router.include_router(portfolio.router)   # CRUD endpoints
portfolio_router.include_router(risk.router)