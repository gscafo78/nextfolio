"""add price_currency, exchange_rate, fee_currency to transactions

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rinomina il vecchio campo generico "currency" in "price_currency"
    op.alter_column("transactions", "currency", new_column_name="price_currency")

    op.add_column("transactions", sa.Column("exchange_rate", sa.Float(), nullable=False, server_default="1.0"))
    op.add_column("transactions", sa.Column("fee_currency", sa.String(3), nullable=False, server_default="EUR"))


def downgrade() -> None:
    op.drop_column("transactions", "fee_currency")
    op.drop_column("transactions", "exchange_rate")
    op.alter_column("transactions", "price_currency", new_column_name="currency")
