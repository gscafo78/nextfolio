"""Sostituto d'imposta flag su accounts

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "is_sostituto_imposta",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("accounts", "is_sostituto_imposta")
