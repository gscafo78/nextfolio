"""Add user roles, 2FA fields, and user_settings table

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ruoli utente e campi 2FA sulla tabella users
    op.add_column("users", sa.Column("role", sa.String(20), nullable=False, server_default="USER"))
    op.add_column("users", sa.Column("two_factor_secret", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default="false"))

    # Il primo utente registrato diventa SUPERADMIN
    op.execute("UPDATE users SET role = 'SUPERADMIN' WHERE id = (SELECT MIN(id) FROM users WHERE id IS NOT NULL)")

    # Tabella impostazioni personali
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("theme", sa.String(20), nullable=False, server_default="light"),
        sa.Column("display_currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
    op.drop_column("users", "two_factor_enabled")
    op.drop_column("users", "two_factor_secret")
    op.drop_column("users", "role")
