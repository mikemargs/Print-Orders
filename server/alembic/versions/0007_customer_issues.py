"""Add customer issue records and immutable communication history."""
from alembic import op
from app.database import CustomerIssue, IssueActivity

revision = '0007_customer_issues'
down_revision = '0006_percent_discounts'
branch_labels = None
depends_on = None


def upgrade():
    CustomerIssue.__table__.create(op.get_bind())
    IssueActivity.__table__.create(op.get_bind())


def downgrade():
    IssueActivity.__table__.drop(op.get_bind())
    CustomerIssue.__table__.drop(op.get_bind())
