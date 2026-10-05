"""Add percent discount fields to work orders."""
import sqlalchemy as sa
from alembic import op

revision = "0006_percent_discounts"
down_revision = "0005_artwork_files"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "work_orders",
        sa.Column("discount_mode", sa.String(length=10), nullable=False, server_default="amount"),
    )
    op.add_column(
        "work_orders",
        sa.Column("discount_percent", sa.Numeric(7, 4), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("work_orders", "discount_percent")
    op.drop_column("work_orders", "discount_mode")
