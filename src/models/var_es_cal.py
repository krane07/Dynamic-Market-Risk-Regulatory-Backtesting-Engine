from datetime import datetime
from sqlalchemy import func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from src.models.portfolio_header import portfolio_header

class var_es_cal(Base):
    """VaR and ES Table
    Stores Calculated VaR and ES for the portfolios
    """

    __tablename__ = "var_es_cal"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    date: Mapped[datetime] = mapped_column(server_default=func.now())
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolio_header.portfolio_id"))
    predicted_1d_var: Mapped[float] = mapped_column()
    predicted_10d_var: Mapped[float] = mapped_column()
    predicted_stressed_es: Mapped[float] = mapped_column()
    actual_1d_pnl: Mapped[float] = mapped_column()
    is_exception: Mapped[bool] = mapped_column()