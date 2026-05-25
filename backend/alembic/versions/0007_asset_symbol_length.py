"""extend asset symbol to VARCHAR(50)

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("assets", "symbol", type_=sa.String(50), existing_nullable=False)


def downgrade() -> None:
    op.alter_column("assets", "symbol", type_=sa.String(20), existing_nullable=False)
