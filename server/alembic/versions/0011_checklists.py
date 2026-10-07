"""Add operational checklist templates and runs."""

import sqlalchemy as sa
from alembic import op

revision = "0011_checklists"
down_revision = "0010_shipping_cases"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "checklist_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("checklist_type", sa.String(length=30), nullable=False),
        sa.Column("cadence", sa.String(length=30), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_checklist_templates_company_id"), "checklist_templates", ["company_id"], unique=False)
    op.create_index(op.f("ix_checklist_templates_location_id"), "checklist_templates", ["location_id"], unique=False)
    op.create_index("ix_checklist_template_company_store_active", "checklist_templates", ["company_id", "location_id", "active"], unique=False)

    op.create_table(
        "checklist_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("item_states", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["checklist_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "location_id", "template_id", "business_date", name="uq_checklist_run_template_date"),
    )
    op.create_index(op.f("ix_checklist_runs_company_id"), "checklist_runs", ["company_id"], unique=False)
    op.create_index(op.f("ix_checklist_runs_location_id"), "checklist_runs", ["location_id"], unique=False)
    op.create_index(op.f("ix_checklist_runs_template_id"), "checklist_runs", ["template_id"], unique=False)
    op.create_index(op.f("ix_checklist_runs_business_date"), "checklist_runs", ["business_date"], unique=False)
    op.create_index(op.f("ix_checklist_runs_status"), "checklist_runs", ["status"], unique=False)
    op.create_index("ix_checklist_run_company_store_date", "checklist_runs", ["company_id", "location_id", "business_date"], unique=False)


def downgrade():
    op.drop_table("checklist_runs")
    op.drop_table("checklist_templates")
