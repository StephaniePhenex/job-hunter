"""URLs the user marked as applied; survives full ``jobs`` table replacement."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AppliedUrl(Base):
    """One row per normalized application URL."""

    __tablename__ = "applied_urls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url_norm: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
