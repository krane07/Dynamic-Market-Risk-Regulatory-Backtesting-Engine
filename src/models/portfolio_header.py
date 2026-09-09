from typing import List
from datetime import datetime
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.portfolio_composition import portfolio_composition

class porfolio_header(Base):
    """Portfolios
    Stores name of the portfolio created by user
    """
    __tablename__ = "portfolio_header"
    portfolio_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    portfolio_name: Mapped[str] = mapped_column(String)
    creation_date: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_date: Mapped[datetime] = mapped_column(
        server_default=func.now, onupdate=func.now()
        )
    
    components: Mapped[List["portfolio_composition"]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan"
        )