"""Add employee authentication version."""
import sqlalchemy as sa
from alembic import op

revision='0003_employee_auth_version'
down_revision='0002_scope_processed_operations'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('employees', sa.Column('auth_version', sa.Integer(), nullable=False, server_default='1'))

def downgrade():
    op.drop_column('employees','auth_version')
