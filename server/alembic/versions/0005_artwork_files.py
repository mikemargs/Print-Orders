"""Add artwork attachment metadata."""
import sqlalchemy as sa
from alembic import op

revision = "0005_artwork_files"
down_revision = "0004_fixed_precision_money"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "artwork_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("work_order_id", sa.String(length=36), sa.ForeignKey("work_orders.id"), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=160), nullable=False, server_default="application/octet-stream"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by", sa.String(length=36), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("object_key", name="uq_artwork_file_object_key"),
    )
    op.create_index("ix_artwork_files_company_id", "artwork_files", ["company_id"])
    op.create_index("ix_artwork_files_work_order_id", "artwork_files", ["work_order_id"])
    op.create_index("ix_artwork_files_active", "artwork_files", ["active"])


def downgrade():
    op.drop_index("ix_artwork_files_active", table_name="artwork_files")
    op.drop_index("ix_artwork_files_work_order_id", table_name="artwork_files")
    op.drop_index("ix_artwork_files_company_id", table_name="artwork_files")
    op.drop_table("artwork_files")
