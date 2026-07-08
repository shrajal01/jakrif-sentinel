from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.circuit_breaker import CircuitBreaker
    from app.models.retry_attempt import RetryAttempt
    from app.models.request_log import RequestLog
    from app.models.health_snapshot import HealthSnapshot

class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    circuit_breakers: Mapped[List["CircuitBreaker"]] = relationship(back_populates="service", cascade="all, delete-orphan")
    retry_attempts: Mapped[List["RetryAttempt"]] = relationship(back_populates="service", cascade="all, delete-orphan")
    request_logs: Mapped[List["RequestLog"]] = relationship(back_populates="service", cascade="all, delete-orphan")
    health_snapshots: Mapped[List["HealthSnapshot"]] = relationship(back_populates="service", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Service(id={self.id}, name='{self.name}', is_enabled={self.is_enabled})>"
