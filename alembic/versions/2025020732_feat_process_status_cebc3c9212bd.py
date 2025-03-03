"""feat : process_status

Revision ID: cebc3c9212bd
Revises: e9565d0efea9
Create Date: 2025-02-07 11:32:16.831790

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision = "cebc3c9212bd"
down_revision = "e9565d0efea9"
branch_labels = None
depends_on = None

# Define the new enum type with 'PENDING' added
new_enum_type = ENUM(
    "NOT_STARTED",
    "STARTED",
    "IN_PROGRESS",
    "COMPLETED",
    "FAILED",
    "PENDING",  # Newly added value
    name="status",
    create_type=False,  # Prevent recreation of type if it exists
)

old_enum_type = ENUM(
    "NOT_STARTED",
    "STARTED",
    "IN_PROGRESS",
    "COMPLETED",
    "FAILED",
    name="status",
    create_type=False,  # Use existing enum
)

def upgrade():
    # Alter the existing ENUM to include "PENDING"
    op.execute("ALTER TYPE status ADD VALUE 'PENDING'")

    # Add the new column to session_screening_status
    op.add_column(
        "session_screening_status",
        sa.Column(
            "process_status",
            new_enum_type,
            nullable=False,
            server_default="PENDING",
        ),
    )

def downgrade():
    # Remove the column from session_screening_status
    op.drop_column("session_screening_status", "process_status")

    # Enum rollback: Note that PostgreSQL does not support removing values from ENUMs.
    # One workaround is to create a new enum type without 'PENDING', rename columns, and drop the old type.
    op.execute("ALTER TABLE session_screening_status ALTER COLUMN process_status TYPE status USING process_status::text::status")