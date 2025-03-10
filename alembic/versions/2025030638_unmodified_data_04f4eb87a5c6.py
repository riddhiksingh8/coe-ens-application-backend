"""unmodified data

Revision ID: 04f4eb87a5c6
Revises: 641b9c0f2cfb
Create Date: 2025-03-06 13:38:14.957842

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "04f4eb87a5c6"
down_revision = "641b9c0f2cfb"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("unmodified_name", sa.String(), nullable=True),
    )
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("unmodified_name_international", sa.String(), nullable=True),
    )
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("unmodified_address", sa.Text(), nullable=True),
    )
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("unmodified_postcode", sa.String(), nullable=True),
    )
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("unmodified_city", sa.String(), nullable=True),
    )
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("unmodified_country", sa.String(), nullable=True),
    )
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("unmodified_phone_or_fax", sa.String(), nullable=True),
    )
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("unmodified_email_or_website", sa.String(), nullable=True),
    )
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("unmodified_national_id", sa.String(), nullable=True),
    )
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("unmodified_state", sa.String(), nullable=True),
    )
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("unmodified_address_type", sa.String(), nullable=True),
    )

def downgrade():
    pass
