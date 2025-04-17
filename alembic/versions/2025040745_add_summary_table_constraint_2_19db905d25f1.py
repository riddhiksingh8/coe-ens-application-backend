"""add_summary_table_constraint_2

Revision ID: 19db905d25f1
Revises: c7b40604a362
Create Date: 2025-04-07 16:45:13.413075

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

# revision identifiers, used by Alembic.
revision = "19db905d25f1"
down_revision = "c7b40604a362"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = reflection.Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns('summary')]

    op.drop_constraint("unique_ens_session_summary", "summary", type_="unique")

    if 'ens_id' in columns:
        op.create_unique_constraint(
            "unique_ens_session_summary",
            "summary",
            ["ens_id", "session_id", "area"]
        )
    else:
        print("Column 'ens_id' not found!")


def downgrade():
    pass
