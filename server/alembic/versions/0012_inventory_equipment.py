"""Add inventory and equipment management."""

import sqlalchemy as sa
from alembic import op

revision = "0012_inventory_equipment"
down_revision = "0011_operations_checklists"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=220), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("reorder_point", sa.Numeric(12, 2), nullable=False),
        sa.Column("target_stock", sa.Numeric(12, 2), nullable=False),
        sa.Column("cost_per_unit", sa.Numeric(12, 2), nullable=False),
        sa.Column("vendor", sa.String(length=180), nullable=False),
        sa.Column("vendor_sku", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
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
    op.create_index("ix_inventory_company_store_active", "inventory_items", ["company_id", "location_id", "active"])
    op.create_index("ix_inventory_company_name", "inventory_items", ["company_id", "name"])

    op.create_table(
        "inventory_adjustments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("change_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("resulting_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(length=60), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("adjusted_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["adjusted_by"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_adjustment_item_time", "inventory_adjustments", ["item_id", "created_at"])

    op.create_table(
        "equipment_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=220), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("asset_tag", sa.String(length=100), nullable=False),
        sa.Column("manufacturer", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("serial_number", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("warranty_expiration", sa.Date(), nullable=True),
        sa.Column("vendor", sa.String(length=180), nullable=False),
        sa.Column("service_provider", sa.String(length=180), nullable=False),
        sa.Column("next_service_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
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
    op.create_index("ix_equipment_company_store_status", "equipment_assets", ["company_id", "location_id", "status"])
    op.create_index("ix_equipment_next_service", "equipment_assets", ["company_id", "next_service_date"])

    op.create_table(
        "equipment_service_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("equipment_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=180), nullable=False),
        sa.Column("cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("recorded_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment_assets.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_equipment_service_asset_date", "equipment_service_events", ["equipment_id", "event_date"])


def downgrade():
    op.drop_table("equipment_service_events")
    op.drop_table("equipment_assets")
    op.drop_table("inventory_adjustments")
    op.drop_table("inventory_items")
