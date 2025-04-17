"""upload supplier data default chanage

Revision ID: 3ec6986edefd
Revises: f7fba615e296
Create Date: 2025-04-08 12:20:29.740104

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "3ec6986edefd"
down_revision = "f7fba615e296"
branch_labels = None
depends_on = None


def upgrade():
    # Add new enum values to existing PostgreSQL enum type
    op.execute("ALTER TYPE finalvalidatedstatus ADD VALUE IF NOT EXISTS 'AUTO_REJECT'")
    op.execute("ALTER TYPE finalvalidatedstatus ADD VALUE IF NOT EXISTS 'AUTO_ACCEPT'")
    op.execute("ALTER TYPE finalvalidatedstatus ADD VALUE IF NOT EXISTS 'REVIEW'")
def downgrade():
    pass