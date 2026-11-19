"""Permessi di scrittura e cancellazione sui token MCP

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mcp_access_tokens", sa.Column("can_write", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("mcp_access_tokens", sa.Column("can_delete", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("mcp_access_tokens", "can_delete")
    op.drop_column("mcp_access_tokens", "can_write")
