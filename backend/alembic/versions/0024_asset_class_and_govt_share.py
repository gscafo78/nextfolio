"""Aggiunge asset_class_override e govt_bond_share su assets

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("asset_class_override", sa.String(20), nullable=True))
    op.add_column("assets", sa.Column("govt_bond_share", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "govt_bond_share")
    op.drop_column("assets", "asset_class_override")
