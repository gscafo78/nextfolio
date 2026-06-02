"""Watchlist — asset monitorati senza transazioni

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist",
        sa.Column("id",           sa.Integer(),     primary_key=True),
        sa.Column("user_id",      sa.Integer(),     sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id",     sa.Integer(),     sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note",         sa.Text(),        nullable=True),
        sa.Column("target_price", sa.Float(),       nullable=True),
        sa.Column("added_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "asset_id", name="uq_watchlist_user_asset"),
    )
    # indice separato da create_table per evitare conflitti di nomi con index=True
    op.create_index("ix_watchlist_user_id", "watchlist", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_watchlist_user_id", table_name="watchlist")
    op.drop_table("watchlist")
