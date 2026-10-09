"""Add company-wide work order defaults."""

import sqlalchemy as sa
from alembic import op

revision = "0014_company_settings"
down_revision = "0013_product_pricing_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("companies", sa.Column("default_tax_rate", sa.Numeric(7, 4), nullable=False, server_default="0"))
    op.add_column("companies", sa.Column("default_order_priority", sa.String(20), nullable=False, server_default="Normal"))
    op.add_column("companies", sa.Column("default_delivery_method", sa.String(20), nullable=False, server_default="Pickup"))
    op.add_column("companies", sa.Column("settings_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    for column in ("settings_version", "default_delivery_method", "default_order_priority", "default_tax_rate"):
        op.drop_column("companies", column)
