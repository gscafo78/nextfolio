"""add language to user_settings

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("language", sa.String(5), nullable=False, server_default="it"))


def downgrade() -> None:
    op.drop_column("user_settings", "language")
