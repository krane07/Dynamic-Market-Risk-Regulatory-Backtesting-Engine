from fastapi import APIRouter
from src.routers.prices import prices, risk

prices_router = APIRouter(prefix="price")

prices_router.include_router(prices.router)
prices_router.include_router(risk.router)