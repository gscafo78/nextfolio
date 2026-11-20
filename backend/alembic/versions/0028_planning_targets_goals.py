"""Allocazione obiettivo e obiettivi di capitale (pagina Pianifica)

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-20
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planning_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weights", JSONB, nullable=False, server_default="{}"),
        sa.Column("tolerance_pct", sa.Float(), nullable=False, server_default="5"),
        sa.Column("preferred", JSONB, nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_planning_targets_user"),
    )
    op.create_table(
        "planning_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("target_amount", sa.Float(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("monthly_contribution", sa.Float(), nullable=False, server_default="0"),
        sa.Column("initial_amount", sa.Float(), nullable=True),
        sa.Column("inflation_pct", sa.Float(), nullable=False, server_default="2"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_planning_goals_user_id", "planning_goals", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_planning_goals_user_id", table_name="planning_goals")
    op.drop_table("planning_goals")
    op.drop_table("planning_targets")
