"""Tabella account_balances: saldo di cassa per conto e data

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("balance", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "date", name="uq_account_balances_account_date"),
    )
    op.create_index("ix_account_balances_account_id", "account_balances", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_account_balances_account_id", table_name="account_balances")
    op.drop_table("account_balances")
