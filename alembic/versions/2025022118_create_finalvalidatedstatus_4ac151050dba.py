"""create FinalValidatedStatus

Revision ID: 4ac151050dba
Revises: 664700be9a80
Create Date: 2025-02-21 15:18:52.107499

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.sql import expression
from alembic import op

# revision identifiers, used by Alembic.
revision = "4ac151050dba"
down_revision = "664700be9a80"
branch_labels = None
depends_on = None

final_validation_status_enum = ENUM("VALIDATED",
                "NOT_VALIDATED",
                "NOT_REQUIRED",
                "PENDING",
                "FAILED",
                name='finalvalidatedstatus')

def upgrade():
    # Ensure the ENUM type is created before usage
    final_validation_status_enum.create(op.get_bind(), checkfirst=True)

    # Add the new column with ENUM type
    op.add_column(
        "upload_supplier_master_data",
        sa.Column(
            "final_validation_status",
            final_validation_status_enum,
            server_default=expression.literal('PENDING'),
            nullable=False,
        ),
    )

    # Update NULL values in bvd_id before altering the column
    op.execute("UPDATE supplier_master_data SET bvd_id = 'UNKNOWN' WHERE bvd_id IS NULL")

    # Now safely set NOT NULL constraint
    op.alter_column(
        'supplier_master_data', 
        'bvd_id',
        existing_type=sa.String(50),
        nullable=False
    )

def downgrade():
    # Revert the NOT NULL constraint change
    op.alter_column(
        'supplier_master_data', 
        'bvd_id',
        existing_type=sa.String(50),
        nullable=True
    )

    # Remove the column
    op.drop_column("upload_supplier_master_data", "final_validation_status")

    # Drop ENUM type (only if it’s no longer used in the DB)
    final_validation_status_enum.drop(op.get_bind(), checkfirst=True)
