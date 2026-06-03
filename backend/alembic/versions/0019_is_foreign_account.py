"""Aggiunge is_foreign su accounts (IVAFE)

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "is_foreign",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("accounts", "is_foreign")
