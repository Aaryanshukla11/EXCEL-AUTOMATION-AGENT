"""Initial schema migration: creates system_metadata and schema_migrations tables.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-23 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_metadata",
        sa.Column("key", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )

    op.create_table(
        "schema_migrations",
        sa.Column("version", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("schema_migrations")
    op.drop_table("system_metadata")
