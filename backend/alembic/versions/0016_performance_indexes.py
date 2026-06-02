"""Add performance indexes on hot query paths

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-02

Motivazioni:
- transactions(asset_id): FIFO e calcolo portafoglio iterano per asset; era indicizzata
  solo per account_id e date.
- transactions(account_id, asset_id): calcoli per-conto in portfolio/allocation.
- price_alerts(is_active, asset_id): il task Celery check_price_alerts (ogni 5 min)
  filtra prima per is_active=true, poi per asset_id.
- price_history(asset_id, date DESC): la query "ultimo prezzo" usa ORDER BY date DESC;
  il vincolo unique crea un indice ASC; quello DESC ottimizza get_latest_price().
"""
import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── transactions ────────────────────────────────────────────────────────
    op.create_index(
        "ix_transactions_asset_id",
        "transactions",
        ["asset_id"],
    )
    op.create_index(
        "ix_transactions_account_asset",
        "transactions",
        ["account_id", "asset_id"],
    )

    # ── price_alerts ────────────────────────────────────────────────────────
    op.create_index(
        "ix_price_alerts_active_asset",
        "price_alerts",
        ["is_active", "asset_id"],
    )

    # ── price_history — indice DESC per "prezzo più recente" ────────────────
    op.create_index(
        "ix_price_history_asset_date_desc",
        "price_history",
        [sa.text("asset_id"), sa.text("date DESC")],
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("ix_price_history_asset_date_desc", table_name="price_history")
    op.drop_index("ix_price_alerts_active_asset",     table_name="price_alerts")
    op.drop_index("ix_transactions_account_asset",    table_name="transactions")
    op.drop_index("ix_transactions_asset_id",         table_name="transactions")
