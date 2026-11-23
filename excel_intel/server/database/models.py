"""SQLAlchemy Declarative Base and foundational database models.

Follows the SQLite WAL storage strategy defined in Milestone B0.
"""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""

    pass


class SystemMetadataRecord(Base):
    """Stores key-value system metadata and migration milestones."""

    __tablename__ = "system_metadata"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<SystemMetadataRecord(key={self.key!r})>"


class SchemaMigrationRecord(Base):
    """Tracks applied database schema versions and timestamps."""

    __tablename__ = "schema_migrations"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    applied_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<SchemaMigrationRecord(version={self.version!r})>"


class StagedWorkbookRecord(Base):
    """Stores metadata and physical storage pointers for staged workbooks."""

    __tablename__ = "staged_workbooks"

    workbook_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    package_type: Mapped[str] = mapped_column(String(16), nullable=False)
    has_macros: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_1904: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sheet_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sheet_names: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="staged", nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, default="default", nullable=False)
    staged_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<StagedWorkbookRecord(id={self.workbook_id!r}, filename={self.filename!r}, sha256={self.sha256[:8]!r})>"
