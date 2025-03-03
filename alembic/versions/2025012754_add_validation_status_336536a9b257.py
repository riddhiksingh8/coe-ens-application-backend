"""add validation_status

Revision ID: 336536a9b257
Revises: b4e928f31177
Create Date: 2025-01-27 16:54:22.361561

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.sql import expression

# revision identifiers, used by Alembic.
revision = "336536a9b257"
down_revision = "b4e928f31177"
branch_labels = None
depends_on = None

# Define the ValidationStatus Enum for PostgreSQL
validationstatus_enum = ENUM('MATCH', 'NO_MATCH', 'PENDING', name='validationstatus', create_type=False)

def upgrade():
    # Create the validationstatus enum type in PostgreSQL
    validationstatus_enum.create(op.get_bind(), checkfirst=True)
    
    # Add the validation_status column with the enum type and a default value of 'PENDING'
    op.add_column(
        'upload_supplier_master_data',
        sa.Column(
            'validation_status',
            validationstatus_enum,
            nullable=False,
            server_default=expression.literal('PENDING')  # Set default to 'PENDING'
        )
    )

def downgrade():
    # Drop the validation_status column
    op.drop_column('upload_supplier_master_data', 'validation_status')

    # Drop the validationstatus enum type if no longer needed
    validationstatus_enum.drop(op.get_bind(), checkfirst=True)