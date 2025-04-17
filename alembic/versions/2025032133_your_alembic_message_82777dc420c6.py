"""<your alembic message>

Revision ID: 82777dc420c6
Revises: b65459278957
Create Date: 2025-03-21 19:33:36.349661

"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "82777dc420c6"
down_revision = "b65459278957"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("uploaded_external_vendor_id", sa.String(), nullable=True),
    )


def downgrade():
    pass
