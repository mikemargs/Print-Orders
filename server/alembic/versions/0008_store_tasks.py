"""add store tasks

Revision ID: 0008_store_tasks
Revises: 0007_customer_issues
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_store_tasks"
down_revision = "0007_customer_issues"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "store_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("location_id", sa.String(length=36), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="Open"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="Normal"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("assigned_employee_id", sa.String(length=36), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("work_order_id", sa.String(length=36), sa.ForeignKey("work_orders.id"), nullable=True),
        sa.Column("issue_id", sa.String(length=36), sa.ForeignKey("customer_issues.id"), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    for name, column in [
        ("ix_store_tasks_company_id", "company_id"),
        ("ix_store_tasks_location_id", "location_id"),
        ("ix_store_tasks_status", "status"),
        ("ix_store_tasks_due_date", "due_date"),
        ("ix_store_tasks_assigned_employee_id", "assigned_employee_id"),
        ("ix_store_tasks_customer_id", "customer_id"),
        ("ix_store_tasks_work_order_id", "work_order_id"),
        ("ix_store_tasks_issue_id", "issue_id"),
    ]:
        op.create_index(name, "store_tasks", [column])
    op.create_index(
        "ix_task_company_store_status",
        "store_tasks",
        ["company_id", "location_id", "status"],
    )
    op.create_index("ix_task_company_due", "store_tasks", ["company_id", "due_date"])


def downgrade():
    op.drop_table("store_tasks")
