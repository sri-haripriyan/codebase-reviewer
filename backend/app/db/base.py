"""SQLAlchemy declarative base and common mixins."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy domain models."""

    pass


class UUIDPrimaryKeyMixin:
    """Mixin providing a consistent UUIDv4 primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        doc="Unique identifier (UUIDv4)",
    )

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("id", uuid.uuid4())
        super().__init__(**kwargs)


class TimestampMixin:
    """Mixin providing timezone-aware created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
        doc="Record creation timestamp (timezone-aware UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        onupdate=utc_now,
        nullable=False,
        doc="Record last updated timestamp (timezone-aware UTC)",
    )
