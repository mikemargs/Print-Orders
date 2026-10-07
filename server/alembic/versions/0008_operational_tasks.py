"""Add operational tasks and follow-ups."""

import sqlalchemy as sa
from alembic import op

revision = "0008_operational_tasks"
down_revision = "0007_customer_issues"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operational_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("assigned_employee_id", sa.String(length=36), nullable=True),
        sa.Column("customer_id", sa.String(length=36), nullable=True),
        sa.Column("work_order_id", sa.String(length=36), nullable=True),
        sa.Column("customer_issue_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["assigned_employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.ForeignKeyConstraint(["customer_issue_id"], ["customer_issues.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_company_location_status", "operational_tasks", ["company_id", "location_id", "status"])
    op.create_index(op.f("ix_operational_tasks_company_id"), "operational_tasks", ["company_id"], unique=False)
    op.create_index(op.f("ix_operational_tasks_location_id"), "operational_tasks", ["location_id"], unique=False)
    op.create_index(op.f("ix_operational_tasks_due_date"), "operational_tasks", ["due_date"], unique=False)
    op.create_index(op.f("ix_operational_tasks_assigned_employee_id"), "operational_tasks", ["assigned_employee_id"], unique=False)


def downgrade():
    op.drop_table("operational_tasks")
