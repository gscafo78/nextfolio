"""add zen_mode to user_settings

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("zen_mode", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("user_settings", "zen_mode")
