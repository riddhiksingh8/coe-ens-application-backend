"""user_id

Revision ID: 50c9a414ea0f
Revises: 04f4eb87a5c6
Create Date: 2025-03-13 12:57:41.454180

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "50c9a414ea0f"
down_revision = "04f4eb87a5c6"
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add user_id column as NULLABLE
    op.add_column(
        "upload_supplier_master_data",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users_table.user_id", ondelete="CASCADE"), nullable=True),
    )

    # Step 2: Backfill existing records with a valid user_id (pick any valid user from users_table)
    op.execute(
        """
        UPDATE upload_supplier_master_data 
        SET user_id = (SELECT user_id FROM users_table LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    # Step 3: Enforce NOT NULL constraint
    op.alter_column("upload_supplier_master_data", "user_id", nullable=False)

def downgrade():
    pass
