from pydantic import BaseModel, Field
from typing import Literal

class Portfolio(BaseModel):
    name: str
    holdings: dict[str, float]          # {ticker: qty}

class HoldingsBody(BaseModel):
    holdings: dict[str, float]

class RiskRequest(BaseModel):
    holdings: dict[str, float]
    confidence: float = Field(0.95, gt=0.5, lt=1)
    horizon_days: int = Field(1, ge=1)
    method: Literal["historical", "parametric"] = "historical"
    lookback_days: int = 500