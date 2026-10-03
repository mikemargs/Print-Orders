"""Use fixed precision numeric order totals."""
import sqlalchemy as sa
from alembic import op

revision='0004_fixed_precision_money'
down_revision='0003_employee_auth_version'
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table('work_orders') as batch:
        batch.alter_column('tax_rate', existing_type=sa.Float(), type_=sa.Numeric(7,4), existing_nullable=False)
        for name in ('deposit','discount','subtotal','total','balance'):
            batch.alter_column(name, existing_type=sa.Float(), type_=sa.Numeric(12,2), existing_nullable=False)

def downgrade():
    with op.batch_alter_table('work_orders') as batch:
        batch.alter_column('tax_rate', existing_type=sa.Numeric(7,4), type_=sa.Float(), existing_nullable=False)
        for name in ('deposit','discount','subtotal','total','balance'):
            batch.alter_column(name, existing_type=sa.Numeric(12,2), type_=sa.Float(), existing_nullable=False)
