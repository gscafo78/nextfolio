"""Scenari della pagina Pianifica

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planning_scenarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("use_cash", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_planning_scenarios_user_id", "planning_scenarios", ["user_id"])
    op.create_table(
        "planning_scenario_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scenario_id", sa.Integer(), sa.ForeignKey("planning_scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symbol", sa.String(50), nullable=True),
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("exchange", sa.String(20), nullable=True),
        sa.Column("amount_eur", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("price_eur", sa.Float(), nullable=True),
        sa.Column("fee_eur", sa.Float(), nullable=False, server_default="0"),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_planning_scenario_items_scenario_id", "planning_scenario_items", ["scenario_id"])


def downgrade() -> None:
    op.drop_index("ix_planning_scenario_items_scenario_id", table_name="planning_scenario_items")
    op.drop_table("planning_scenario_items")
    op.drop_index("ix_planning_scenarios_user_id", table_name="planning_scenarios")
    op.drop_table("planning_scenarios")
