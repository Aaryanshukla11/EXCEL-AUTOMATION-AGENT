"""Workbook staging schema migration: creates staged_workbooks table.

Revision ID: 0002_workbook_staging
Revises: 0001_initial_schema
Create Date: 2026-11-23 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_workbook_staging"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staged_workbooks",
        sa.Column("workbook_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("package_type", sa.String(length=16), nullable=False),
        sa.Column("has_macros", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_1904", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("sheet_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sheet_names", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="staged"),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column(
            "staged_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_staged_workbooks_tenant_id",
        "staged_workbooks",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_staged_workbooks_sha256",
        "staged_workbooks",
        ["sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_staged_workbooks_sha256", table_name="staged_workbooks")
    op.drop_index("ix_staged_workbooks_tenant_id", table_name="staged_workbooks")
    op.drop_table("staged_workbooks")
