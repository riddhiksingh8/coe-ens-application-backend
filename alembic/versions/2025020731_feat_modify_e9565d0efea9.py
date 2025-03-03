import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "e9565d0efea9"
down_revision = "20df8125870f"
branch_labels = None
depends_on = None

def upgrade():
    
    # Check if the foreign key constraint already exists, and only add it if it doesn't
    bind = op.get_bind()
    inspector = inspect(bind)

    # Get existing constraints on the refresh_token table
    existing_constraints = [constraint['name'] for constraint in inspector.get_foreign_keys('refresh_token')]

    # Drop and recreate foreign key constraint
    if 'refresh_token_user_id_fkey' in existing_constraints:
        op.drop_constraint("refresh_token_user_id_fkey", "refresh_token", type_="foreignkey")
        
    # Ensure the user_id column in users_table is String (VARCHAR)
    op.alter_column('users_table', 'user_id', type_=sa.String(), existing_type=sa.UUID(), existing_nullable=False)
    
    # Ensure the user_id column in refresh_token is String (VARCHAR)
    op.alter_column('refresh_token', 'user_id', type_=sa.String(), existing_type=sa.UUID(), existing_nullable=False)
    
    
    op.create_foreign_key(
        "refresh_token_user_id_fkey",
        "refresh_token",
        "users_table",
        ["user_id"],
        ["user_id"],
        ondelete="CASCADE"
    )

def downgrade():
    # Revert changes to the user_id column in both tables to UUID
    op.alter_column('refresh_token', 'user_id', type_=sa.UUID(), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('users_table', 'user_id', type_=sa.UUID(), existing_type=sa.String(), existing_nullable=False)
    
    # Drop the foreign key constraint if needed
    op.drop_constraint("refresh_token_user_id_fkey", "refresh_token", type_="foreignkey")
