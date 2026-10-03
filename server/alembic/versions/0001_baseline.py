"""Initial Print Order Manager schema."""
import sqlalchemy as sa
from alembic import op

revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('companies',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('name', sa.String(160), nullable=False),
        sa.Column('code', sa.String(50), nullable=False), sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_companies_code', 'companies', ['code'], unique=True)
    op.create_table('locations',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False), sa.Column('store_number', sa.String(30), nullable=False),
        sa.Column('timezone', sa.String(80), nullable=False), sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_locations_company_id','locations',['company_id'])
    op.create_table('employees',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False), sa.Column('pin_hash', sa.Text(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False), sa.Column('location_ids', sa.JSON(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_employees_company_id','employees',['company_id'])
    op.create_table('customers',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.String(36), nullable=False), sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('company', sa.String(180), nullable=False), sa.Column('first_name', sa.String(100), nullable=False), sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('phone', sa.String(60), nullable=False), sa.Column('email', sa.String(180), nullable=False), sa.Column('address1', sa.String(180), nullable=False),
        sa.Column('address2', sa.String(180), nullable=False), sa.Column('city', sa.String(100), nullable=False), sa.Column('state', sa.String(60), nullable=False),
        sa.Column('postal_code', sa.String(30), nullable=False), sa.Column('tax_exempt', sa.Boolean(), nullable=False), sa.Column('notes', sa.Text(), nullable=False))
    op.create_index('ix_customers_company_id','customers',['company_id']); op.create_index('ix_customers_updated_at','customers',['updated_at'])
    op.create_table('work_orders',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('customer_id', sa.String(36), sa.ForeignKey('customers.id'), nullable=False), sa.Column('location_id', sa.String(36), sa.ForeignKey('locations.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_by', sa.String(36), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False), sa.Column('order_number', sa.String(70), nullable=False), sa.Column('status', sa.String(50), nullable=False),
        sa.Column('priority', sa.String(30), nullable=False), sa.Column('received_date', sa.String(10), nullable=False), sa.Column('due_date', sa.String(10), nullable=False),
        sa.Column('assigned_to', sa.String(120), nullable=False), sa.Column('delivery_method', sa.String(50), nullable=False), sa.Column('po_number', sa.String(80), nullable=False),
        sa.Column('description', sa.String(300), nullable=False), sa.Column('artwork_path', sa.Text(), nullable=False), sa.Column('production_notes', sa.Text(), nullable=False),
        sa.Column('customer_notes', sa.Text(), nullable=False), sa.Column('tax_rate', sa.Float(), nullable=False), sa.Column('deposit', sa.Float(), nullable=False),
        sa.Column('discount', sa.Float(), nullable=False), sa.Column('subtotal', sa.Float(), nullable=False), sa.Column('total', sa.Float(), nullable=False),
        sa.Column('balance', sa.Float(), nullable=False), sa.Column('items', sa.JSON(), nullable=False))
    for name, cols in [('ix_work_orders_company_id',['company_id']),('ix_work_orders_customer_id',['customer_id']),('ix_work_orders_location_id',['location_id']),('ix_work_orders_updated_at',['updated_at']),('ix_work_orders_order_number',['order_number']),('ix_work_orders_status',['status']),('ix_work_orders_due_date',['due_date'])]: op.create_index(name,'work_orders',cols)
    op.create_table('sync_events',
        sa.Column('sequence', sa.Integer(), primary_key=True, autoincrement=True), sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('entity_type', sa.String(30), nullable=False), sa.Column('entity_id', sa.String(36), nullable=False), sa.Column('change_type', sa.String(20), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_sync_events_company_id','sync_events',['company_id'])
    op.create_table('processed_operations',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_processed_operations_company_id','processed_operations',['company_id'])


def downgrade():
    for table in ['processed_operations','sync_events','work_orders','customers','employees','locations','companies']:
        op.drop_table(table)
