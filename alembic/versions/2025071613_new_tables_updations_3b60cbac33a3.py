"""new tables updations

Revision ID: 3b60cbac33a3
Revises: 66c2cc303f0c
Create Date: 2025-07-16 12:13:33.241433

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "3b60cbac33a3"
down_revision = "66c2cc303f0c"
branch_labels = None
depends_on = None


def upgrade():
    # Add unique constraint on ens_id and group_id
    op.create_unique_constraint(
        "uq_ens_group",
        "ens_continuous_group_mapping",  
        ["ens_id", "group_id"]
    )

    # Add city and postcode columns to external_supplier_data
    op.add_column("external_supplier_data", sa.Column("city", sa.String(), nullable=True))
    op.add_column("external_supplier_data", sa.Column("postcode", sa.String(), nullable=True))

    # create new one on primary_id in grid_pm_tracking
    op.create_primary_key("grid_pm_tracking_pkey", "grid_pm_tracking", ["primary_id"])

    # Add kpi_data JSONB column to KPISchemas table
    op.add_column("cyes", sa.Column("kpi_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("fstb", sa.Column("kpi_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("lgrk", sa.Column("kpi_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("news", sa.Column("kpi_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("oval", sa.Column("kpi_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("ovar", sa.Column("kpi_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("rfct", sa.Column("kpi_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("sape", sa.Column("kpi_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("sown", sa.Column("kpi_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Add session_id column to notification table
    op.add_column("notification", sa.Column("session_id", sa.String(), nullable=True))




def downgrade():
    pass
