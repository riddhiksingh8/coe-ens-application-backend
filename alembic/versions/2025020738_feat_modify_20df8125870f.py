import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20df8125870f"
down_revision = "1eac58ddc729"
branch_labels = None
depends_on = None

def upgrade():
    # Ensure the user_id column in users_table is UUID
    op.alter_column(
        "users_table",
        "user_id",
        type_=sa.String(),
        existing_type=sa.Uuid(),
        existing_nullable=False,
        postgresql_using="user_id::uuid"
    )

    # Ensure the user_id column in refresh_token is UUID
    op.alter_column(
        "refresh_token",
        "user_id",
        type_=sa.String(),
        existing_type=sa.Uuid(),
        existing_nullable=False,
        postgresql_using="user_id::uuid"
    )

    # Check if the foreign key constraint already exists, and only add it if it doesn't
    bind = op.get_bind()
    inspector = inspect(bind)

    # Get existing constraints on the refresh_token table
    existing_constraints = [constraint['name'] for constraint in inspector.get_foreign_keys('refresh_token')]

    if 'refresh_token_user_id_fkey' not in existing_constraints:
        op.create_foreign_key(
            "refresh_token_user_id_fkey",
            "refresh_token",
            "users_table",
            ["user_id"],
            ["user_id"],
            ondelete="CASCADE"
        )

def downgrade():
    # Revert changes to the refresh_token user_id column
    op.alter_column(
        "refresh_token",
        "user_id",
        type_=sa.Uuid(),
        existing_type= sa.String(),
        existing_nullable=False
    )

    # Revert changes to the users_table user_id column
    op.alter_column(
        "users_table",
        "user_id",
        type_=sa.Uuid(),
        existing_type= sa.String(),
        existing_nullable=False
    )

    # Drop the foreign key constraint if needed
    op.drop_constraint("refresh_token_user_id_fkey", "refresh_token", type_="foreignkey")
