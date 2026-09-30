import datetime
from sqlalchemy import String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base

class HistoricalData(Base):
    """Historical data record.
    Stores historical data of a tickers as well as log  returns.
    """
    __tablename__ = "historical_data"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_ticker_date"),
        Index("ix_ticker_date", "ticker", "date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[datetime.date] = mapped_column()
    ticker: Mapped[str] = mapped_column(String(30))
    adj_close: Mapped[float] = mapped_column(nullable=True)
    log_return: Mapped[float] = mapped_column(nullable=True)