from datetime import datetime
from sqlalchemy import Float, Integer, String, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.portfolio_header import portfolio_header

class portfolio_composition(Base):
    """Portfolio Components
    Gives information regarding the ticker in the portfolio
    as well as its corresponding weight and when it was added in the portfolio
    """

    __tablename__ = "portfolio_composition"
    id: Mapped[int]= mapped_column(primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio_header.portfolio_id",ondelete="CASCADE")
        )
    ticker: Mapped[str] = mapped_column(String(10))
    buy_price: Mapped[float] = mapped_column(Float)
    units: Mapped[int] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(nullable=False)
    date_established: Mapped[datetime] = mapped_column(server_default=func.now())

    portfolio: Mapped["portfolio_header"] = relationship(back_populates="components")