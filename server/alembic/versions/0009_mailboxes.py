"""Add mailbox management records."""

import sqlalchemy as sa
from alembic import op

revision = "0009_mailboxes"
down_revision = "0008_operational_tasks"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mailboxes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("mailbox_number", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("renewal_date", sa.Date(), nullable=True),
        sa.Column("balance_due", sa.Numeric(12, 2), nullable=False),
        sa.Column("primary_id_on_file", sa.Boolean(), nullable=False),
        sa.Column("secondary_id_on_file", sa.Boolean(), nullable=False),
        sa.Column("form_1583_complete", sa.Boolean(), nullable=False),
        sa.Column("msa_complete", sa.Boolean(), nullable=False),
        sa.Column("phone_verified", sa.Boolean(), nullable=False),
        sa.Column("forwarding_status", sa.String(length=30), nullable=False),
        sa.Column("forwarding_address", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "location_id", "mailbox_number", name="uq_mailbox_company_store_number"),
    )
    op.create_index(op.f("ix_mailboxes_company_id"), "mailboxes", ["company_id"], unique=False)
    op.create_index(op.f("ix_mailboxes_location_id"), "mailboxes", ["location_id"], unique=False)
    op.create_index(op.f("ix_mailboxes_customer_id"), "mailboxes", ["customer_id"], unique=False)
    op.create_index(op.f("ix_mailboxes_status"), "mailboxes", ["status"], unique=False)
    op.create_index(op.f("ix_mailboxes_renewal_date"), "mailboxes", ["renewal_date"], unique=False)
    op.create_index("ix_mailboxes_company_store_status", "mailboxes", ["company_id", "location_id", "status"], unique=False)


def downgrade():
    op.drop_table("mailboxes")
