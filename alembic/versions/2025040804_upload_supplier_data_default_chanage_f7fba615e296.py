"""upload supplier data default chanage

Revision ID: f7fba615e296
Revises: a880fbdcf707
Create Date: 2025-04-08 12:04:07.575757

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "f7fba615e296"
down_revision = "a880fbdcf707"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "upload_supplier_master_data",
        "duplicate_in_session",
        server_default="UNIQUE",
        existing_type=sa.Enum("RETAIN", "REMOVE", "UNIQUE", name="dupinsession"),
    )
def downgrade():
    op.alter_column(
        "upload_supplier_master_data",
        "duplicate_in_session",
        server_default=None,  # or the previous default like "RETAIN"
        existing_type=sa.Enum("RETAIN", "REMOVE", "UNIQUE", name="dupinsession"),
    )