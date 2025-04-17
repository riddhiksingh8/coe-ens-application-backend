"""alembic

Revision ID: b65459278957
Revises: 45d4f94a9d6a
Create Date: 2025-03-20 18:10:40.452540

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b65459278957"
down_revision = "45d4f94a9d6a"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the primary key constraint from the link column
    with op.batch_alter_table('news_master') as batch_op:
        batch_op.drop_constraint('pk_news_master', type_='primary')
        batch_op.create_primary_key('pk_news_master', ['id'])


def downgrade():
    pass
