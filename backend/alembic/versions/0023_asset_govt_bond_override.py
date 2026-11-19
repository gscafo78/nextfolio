"""Aggiunge govt_bond_override su assets (forza il trattamento da titolo di Stato)

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("govt_bond_override", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "govt_bond_override")
