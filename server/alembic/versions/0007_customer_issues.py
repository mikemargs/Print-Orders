"""Add customer issue records and immutable communication history."""

import sqlalchemy as sa
from alembic import op

revision = "0007_customer_issues"
down_revision = "0006_percent_discounts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customer_issues",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("reference", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("assigned_employee_id", sa.String(length=36), nullable=True),
        sa.Column("work_order_id", sa.String(length=36), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("resolution_summary", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_employee_id"],
            ["employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "reference", name="uq_issue_company_reference"),
    )
    op.create_index(
        op.f("ix_customer_issues_assigned_employee_id"),
        "customer_issues",
        ["assigned_employee_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_customer_issues_company_id"), "customer_issues", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_customer_issues_customer_id"), "customer_issues", ["customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_customer_issues_follow_up_date"),
        "customer_issues",
        ["follow_up_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_customer_issues_location_id"), "customer_issues", ["location_id"], unique=False
    )
    op.create_index(op.f("ix_customer_issues_status"), "customer_issues", ["status"], unique=False)
    op.create_index(
        "ix_issue_company_store_status",
        "customer_issues",
        ["company_id", "location_id", "status"],
        unique=False,
    )
    op.create_table(
        "issue_activities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("issue_id", sa.String(length=36), nullable=False),
        sa.Column("activity_type", sa.String(length=30), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("author_employee_id", sa.String(length=36), nullable=False),
        sa.Column("author_name", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_employee_id"],
            ["employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["issue_id"],
            ["customer_issues.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "operation_id", name="uq_issue_activity_operation"),
    )
    op.create_index(
        op.f("ix_issue_activities_company_id"), "issue_activities", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_issue_activities_issue_id"), "issue_activities", ["issue_id"], unique=False
    )
    op.create_index(
        op.f("ix_issue_activities_occurred_at"), "issue_activities", ["occurred_at"], unique=False
    )
    op.create_index(
        "ix_issue_activity_timeline",
        "issue_activities",
        ["issue_id", "occurred_at", "recorded_at"],
        unique=False,
    )


def downgrade():
    op.drop_table("issue_activities")
    op.drop_table("customer_issues")
