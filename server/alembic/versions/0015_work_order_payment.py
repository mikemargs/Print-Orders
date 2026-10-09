"""Add manual paid-in-full status to work orders."""

import sqlalchemy as sa
from alembic import op

revision = "0015_work_order_payment"
down_revision = "0014_company_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("work_orders", sa.Column("paid_in_full", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("work_orders", "paid_in_full")
