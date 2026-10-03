"""Scope processed operation identifiers by company."""
from alembic import op
import sqlalchemy as sa

revision = '0002_scope_processed_operations'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('processed_operations_v2',
        sa.Column('row_id', sa.String(36), primary_key=True),
        sa.Column('operation_id', sa.String(36), nullable=False),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('company_id','operation_id', name='uq_processed_operation_company_operation'))
    op.execute('INSERT INTO processed_operations_v2 (row_id,operation_id,company_id,result,created_at) SELECT id,id,company_id,result,created_at FROM processed_operations')
    op.drop_table('processed_operations')
    op.rename_table('processed_operations_v2','processed_operations')
    op.create_index('ix_processed_operations_company_id','processed_operations',['company_id'])


def downgrade():
    op.create_table('processed_operations_v1',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.execute('INSERT INTO processed_operations_v1 (id,company_id,result,created_at) SELECT operation_id,company_id,result,created_at FROM processed_operations')
    op.drop_table('processed_operations')
    op.rename_table('processed_operations_v1','processed_operations')
    op.create_index('ix_processed_operations_company_id','processed_operations',['company_id'])
