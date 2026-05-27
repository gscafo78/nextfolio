"""add sectors/countries/holdings override fields to assets

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-26
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("sectors_override", JSONB, nullable=True))
    op.add_column("assets", sa.Column("countries_override", JSONB, nullable=True))
    op.add_column("assets", sa.Column("holdings_override", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "holdings_override")
    op.drop_column("assets", "countries_override")
    op.drop_column("assets", "sectors_override")
