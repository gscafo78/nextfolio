"""Bond details — tabella cedole per obbligazioni

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bond_details",
        sa.Column("id",                sa.Integer(),     primary_key=True),
        sa.Column("asset_id",          sa.Integer(),     sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("face_value",        sa.Float(),       nullable=False, server_default="100.0"),
        sa.Column("coupon_rate",       sa.Float(),       nullable=False),   # tasso annuo (es. 0.0165 per 1,65%)
        sa.Column("coupon_frequency",  sa.String(20),    nullable=False),   # ANNUAL|SEMI_ANNUAL|QUARTERLY|MONTHLY
        sa.Column("first_coupon_date", sa.Date(),        nullable=False),   # data prima cedola (ancora calendario)
        sa.Column("maturity_date",     sa.Date(),        nullable=True),    # data scadenza
        sa.Column("issue_date",        sa.Date(),        nullable=True),    # data godimento / emissione
        sa.Column("enriched_from_bi",  sa.Boolean(),     nullable=False, server_default="false"),
    )
    op.create_index("ix_bond_details_asset_id", "bond_details", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_bond_details_asset_id", table_name="bond_details")
    op.drop_table("bond_details")
