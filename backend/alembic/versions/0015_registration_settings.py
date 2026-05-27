"""registration settings and email verification

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tabella impostazioni globali dell'app
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )
    # Valore di default: registrazione pubblica disabilitata
    op.execute("INSERT INTO app_settings (key, value) VALUES ('allow_public_registration', 'false')")

    # Colonne per verifica email su users
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("users", sa.Column("email_verification_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("email_verification_expires", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "email_verification_expires")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "email_verified")
    op.drop_table("app_settings")
