"""add url field to accounts

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-26
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "url")
