from fastapi import FastAPI
from src.routers.portfolio import portfolio_router
from src.routers.prices import prices_router

app = FastAPI(title="Market Risk Calculator")

app.include_router(portfolio_router)
app.include_router(prices_router)

