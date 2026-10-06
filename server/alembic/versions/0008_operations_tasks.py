"""Add shared operations tasks and follow-ups."""

import sqlalchemy as sa
from alembic import op

revision = "0008_operations_tasks"
down_revision = "0007_customer_issues"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operations_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("assigned_employee_id", sa.String(length=36), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("customer_id", sa.String(length=36), nullable=True),
        sa.Column("work_order_id", sa.String(length=36), nullable=True),
        sa.Column("issue_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["issue_id"], ["customer_issues.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "assigned_employee_id",
        "company_id",
        "customer_id",
        "due_date",
        "issue_id",
        "location_id",
        "priority",
        "status",
        "work_order_id",
    ):
        op.create_index(
            op.f(f"ix_operations_tasks_{column}"),
            "operations_tasks",
            [column],
            unique=False,
        )
    op.create_index(
        "ix_operations_task_company_store_status",
        "operations_tasks",
        ["company_id", "location_id", "status"],
        unique=False,
    )


def downgrade():
    op.drop_table("operations_tasks")
