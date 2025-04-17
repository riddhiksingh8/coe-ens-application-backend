"""create summ table

Revision ID: 2eb0c1c9f45f
Revises: 82777dc420c6
Create Date: 2025-04-04 12:25:19.692390

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "2eb0c1c9f45f"
down_revision = "82777dc420c6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'summary',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(length=50), nullable=False),
        sa.Column('ens_id', sa.String(length=50), nullable=True),
        sa.Column('area', sa.String(length=50), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
    )


def downgrade():
    pass
