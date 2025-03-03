"""update validation_status enum

Revision ID: db65ce951064
Revises: b30ed865ac90
Create Date: 2025-01-31 17:55:07.629476

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.sql import expression

# revision identifiers, used by Alembic.
revision = "db65ce951064"
down_revision = "b30ed865ac90"
branch_labels = None
depends_on = None

# Define the Enum types for PostgreSQL
validationstatus_enum = ENUM('VALIDATED', 'NOT_VALIDATED', 'PENDING', name='validationstatus')
finalstatus_enum = ENUM('ACCEPTED', 'REJECTED', 'PENDING', name='finalstatus')
oribismatchstatus_enum = ENUM('MATCH', 'NO_MATCH', 'PENDING', name='oribismatchstatus')
truesightstatus_enum = ENUM('VALIDATED', 'NOT_VALIDATED', 'NOT_REQUIRED', name='truesightstatus')

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Check existing columns in the table
    existing_columns = [col['name'] for col in inspector.get_columns('upload_supplier_master_data')]

    # Only add the column if it does not already exist
    if 'orbis_matched_status' not in existing_columns:
        op.add_column(
            'upload_supplier_master_data',
            sa.Column(
                'orbis_matched_status',
                oribismatchstatus_enum,
                nullable=False,
                server_default=expression.literal('PENDING')  # Set default to 'PENDING'
            )
        )
    # Drop the validation_status column if it exists
    op.drop_column('upload_supplier_master_data', 'validation_status', checkfirst=True)
    op.drop_column('upload_supplier_master_data', 'final_status', checkfirst=True)
    # Alter the existing enum type to add new values (if not already there)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'validationstatus') THEN
                CREATE TYPE validationstatus AS ENUM ('VALIDATED', 'NOT_VALIDATED', 'PENDING');
            ELSE
                -- Add new values to the existing enum type
                ALTER TYPE validationstatus ADD VALUE IF NOT EXISTS 'VALIDATED';
                ALTER TYPE validationstatus ADD VALUE IF NOT EXISTS 'NOT_VALIDATED';
            END IF;
        END $$;
    """)

    # Create the enum types in PostgreSQL if they do not exist
    finalstatus_enum.create(op.get_bind(), checkfirst=True)
    oribismatchstatus_enum.create(op.get_bind(), checkfirst=True)
    truesightstatus_enum.create(op.get_bind(), checkfirst=True)

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

    # Add the final_status column with the enum type and a default value of 'PENDING'
    op.add_column(
        'upload_supplier_master_data',
        sa.Column(
            'final_status',
            finalstatus_enum,
            nullable=False,
            server_default=expression.literal('PENDING')  # Set default to 'PENDING'
        )
    )


def downgrade():
    # Drop the columns
    op.drop_column('upload_supplier_master_data', 'suggested_bvd_id')
    op.drop_column('upload_supplier_master_data', 'truesight_percentage')
    op.drop_column('upload_supplier_master_data', 'matched_percentage')
    op.drop_column('upload_supplier_master_data', 'truesight_status')
    op.drop_column('upload_supplier_master_data', 'orbis_matched_status')
    op.drop_column('upload_supplier_master_data', 'final_status')
    op.drop_column('upload_supplier_master_data', 'validation_status')

    # Drop the enum types if no longer needed
    finalstatus_enum.drop(op.get_bind(), checkfirst=True)
    oribismatchstatus_enum.drop(op.get_bind(), checkfirst=True)
    truesightstatus_enum.drop(op.get_bind(), checkfirst=True)
