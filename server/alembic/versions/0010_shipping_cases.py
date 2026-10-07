"""Add shipping, claims, and GSR tracking records."""

import sqlalchemy as sa
from alembic import op

revision = "0010_shipping_cases"
down_revision = "0009_mailboxes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "shipping_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("customer_issue_id", sa.String(length=36), nullable=True),
        sa.Column("tracking_number", sa.String(length=120), nullable=False),
        sa.Column("carrier", sa.String(length=60), nullable=False),
        sa.Column("service_level", sa.String(length=120), nullable=False),
        sa.Column("case_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("ship_date", sa.Date(), nullable=True),
        sa.Column("promised_date", sa.Date(), nullable=True),
        sa.Column("delivered_date", sa.Date(), nullable=True),
        sa.Column("carrier_reference", sa.String(length=160), nullable=False),
        sa.Column("amount_requested", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount_approved", sa.Numeric(12, 2), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["customer_issue_id"], ["customer_issues.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shipping_cases_company_id"), "shipping_cases", ["company_id"], unique=False)
    op.create_index(op.f("ix_shipping_cases_location_id"), "shipping_cases", ["location_id"], unique=False)
    op.create_index(op.f("ix_shipping_cases_customer_id"), "shipping_cases", ["customer_id"], unique=False)
    op.create_index(op.f("ix_shipping_cases_customer_issue_id"), "shipping_cases", ["customer_issue_id"], unique=False)
    op.create_index(op.f("ix_shipping_cases_tracking_number"), "shipping_cases", ["tracking_number"], unique=False)
    op.create_index(op.f("ix_shipping_cases_status"), "shipping_cases", ["status"], unique=False)
    op.create_index(op.f("ix_shipping_cases_follow_up_date"), "shipping_cases", ["follow_up_date"], unique=False)
    op.create_index("ix_shipping_company_store_status", "shipping_cases", ["company_id", "location_id", "status"], unique=False)


def downgrade():
    op.drop_table("shipping_cases")
