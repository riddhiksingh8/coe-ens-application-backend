"""add_summary_table_constraint

Revision ID: c7b40604a362
Revises: 2eb0c1c9f45f
Create Date: 2025-04-07 14:43:00.870449

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

# revision identifiers, used by Alembic.
revision = "c7b40604a362"
down_revision = "2eb0c1c9f45f"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = reflection.Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns('summary')]

    # op.drop_constraint("unique_ens_session", "summary", type_="unique")

    if 'ens_id' in columns:
        op.create_unique_constraint(
            "unique_ens_session_summary",
            "summary",
            ["ens_id", "session_id"]
        )
    else:
        print("Column 'ens_id' not found!")


def downgrade():
    pass
