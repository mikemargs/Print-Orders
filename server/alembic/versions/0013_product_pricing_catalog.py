"""Add shared product and pricing catalog."""

import sqlalchemy as sa
from alembic import op

revision = "0013_product_pricing_catalog"
down_revision = "0012_inventory_equipment"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "catalog_products",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("source_item_code", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=220), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("manual_price", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=80), nullable=False),
        sa.Column("updated_by", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "source_item_code", name="uq_catalog_company_item_code"),
    )
    op.create_index(
        "ix_catalog_company_active_category",
        "catalog_products",
        ["company_id", "active", "category"],
    )
    op.create_index(
        "ix_catalog_company_name",
        "catalog_products",
        ["company_id", "name"],
    )

    op.create_table(
        "catalog_price_tiers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("min_qty", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_qty", sa.Numeric(12, 2), nullable=True),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("price_unit", sa.Numeric(12, 4), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["catalog_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_catalog_tier_product",
        "catalog_price_tiers",
        ["company_id", "product_id", "sort_order"],
    )

    op.create_table(
        "catalog_import_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("source_key", sa.String(length=120), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("product_count", sa.Integer(), nullable=False),
        sa.Column("price_row_count", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "source_key", name="uq_catalog_import_company_source"),
    )

    op.add_column(
        "inventory_items",
        sa.Column("catalog_product_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_inventory_catalog_product",
        "inventory_items",
        "catalog_products",
        ["catalog_product_id"],
        ["id"],
    )
    op.create_index(
        "ix_inventory_catalog_product",
        "inventory_items",
        ["company_id", "catalog_product_id"],
    )


def downgrade():
    op.drop_index("ix_inventory_catalog_product", table_name="inventory_items")
    op.drop_constraint("fk_inventory_catalog_product", "inventory_items", type_="foreignkey")
    op.drop_column("inventory_items", "catalog_product_id")
    op.drop_table("catalog_import_batches")
    op.drop_table("catalog_price_tiers")
    op.drop_table("catalog_products")
