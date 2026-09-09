from datetime import datetime
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base

class historical_data(Base):
    """Historical data record.
    Stores historical data of a tickers as well as log  returns.
    """
    __tablename__ = "historical_data"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    date: Mapped[datetime] = mapped_column()
    ticker: Mapped[str] = mapped_column(String(10))
    adj_close: Mapped[float] = mapped_column(nullable=True)
    log_return: Mapped[float] = mapped_column(nullable=True)