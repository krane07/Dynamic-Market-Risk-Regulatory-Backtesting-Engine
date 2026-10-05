from __future__ import annotations
from typing import TYPE_CHECKING, List
from datetime import datetime
from sqlalchemy import String, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base

if TYPE_CHECKING:
    from src.models.portfolio_composition import PortfolioComposition

class PortfolioHeader(Base):
    """Portfolios
    Stores name of the portfolio created by user
    """
    __tablename__ = "portfolio_header"
    __table_args = (
            UniqueConstraint("portfolio_name", name="uq_portfolio_name"),
            )
    portfolio_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    creation_date: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_date: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
        )
    
    components: Mapped[List["PortfolioComposition"]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan"
        )