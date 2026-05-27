"""add enrichment fields to assets

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("sectors", JSONB, nullable=True))
    op.add_column("assets", sa.Column("countries", JSONB, nullable=True))
    op.add_column("assets", sa.Column("holdings", JSONB, nullable=True))
    op.add_column("assets", sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "enriched_at")
    op.drop_column("assets", "holdings")
    op.drop_column("assets", "countries")
    op.drop_column("assets", "sectors")
