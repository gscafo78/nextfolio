"""Aggiunge coupon_auto_register su accounts

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "coupon_auto_register",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("accounts", "coupon_auto_register")
