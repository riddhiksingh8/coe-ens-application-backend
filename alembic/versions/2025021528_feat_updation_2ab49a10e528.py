import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2ab49a10e528"
down_revision = "f0df8221baf5"
branch_labels = None
depends_on = None


def upgrade():
    # Add user_group column to refresh_token table
    op.add_column("refresh_token", sa.Column("user_group", sa.String()))


def downgrade():
    pass