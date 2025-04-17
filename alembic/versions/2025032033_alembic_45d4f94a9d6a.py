"""alembic

Revision ID: 45d4f94a9d6a
Revises: 81ae19ffccdb
Create Date: 2025-03-20 12:33:24.724917

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

# revision identifiers, used by Alembic.
revision = "45d4f94a9d6a"
down_revision = "81ae19ffccdb"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = reflection.Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns('news_master')]
    
    if 'news_date' in columns:
        op.create_unique_constraint(
            "unique_name_link_date",
            "news_master",
            ["name", "link", "news_date"]
        )
    else:
        print("Column 'news_date' not found!")





def downgrade():
    pass
