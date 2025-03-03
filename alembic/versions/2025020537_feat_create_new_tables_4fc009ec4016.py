"""feat: create new tables

Revision ID: 4fc009ec4016
Revises: 3c0c27d93f1f
Create Date: 2025-02-05 13:37:39.841517

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op
import enum

# revision identifiers, used by Alembic.
revision = "4fc009ec4016"
down_revision = "3c0c27d93f1f"
branch_labels = None
depends_on = None

# Update or create the Enum type for STATUS
class STATUS(str, enum.Enum):  # Inherit from str to store values as text
    NOT_STARTED = "NOT_STARTED"
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

def upgrade():
    # Create the new Enum type in the database (if not already created)
    status_enum = postgresql.ENUM(
        "NOT_STARTED", "STARTED", "IN_PROGRESS", "COMPLETED", "FAILED", name="status"
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    # Drop the old unique constraint
    op.drop_constraint("unique_ensid_session", "ensid_screening_status", type_="unique")

    # Add the new Unique Constraint on (ens_id, session_id)
    op.create_unique_constraint(
        "unique_ensid_session", "ensid_screening_status", ["ens_id", "session_id"]
    )
    
    # Update columns in `ensid_screening_status` and `session_screening_status` tables
    op.alter_column("ensid_screening_status", "overall_status", type_=status_enum)
    op.alter_column("ensid_screening_status", "orbis_retrieval_status", type_=status_enum)
    op.alter_column("ensid_screening_status", "screening_modules_status", type_=status_enum)
    op.alter_column("ensid_screening_status", "report_generation_status", type_=status_enum)
    
    op.alter_column("session_screening_status", "overall_status", type_=status_enum)
    op.alter_column("session_screening_status", "list_upload_status", type_=status_enum)
    op.alter_column("session_screening_status", "supplier_name_validation_status", type_=status_enum)
    op.alter_column("session_screening_status", "screening_analysis_status", type_=status_enum)

def downgrade():
    # Drop the unique constraint and Enum type
    op.drop_constraint("unique_ensid_session", "ensid_screening_status", type_="unique")

    # Drop the custom Enum type from the database
    status_enum = postgresql.ENUM("NOT_STARTED", "STARTED", "IN_PROGRESS", "COMPLETED", "FAILED", name="status")
    status_enum.drop(op.get_bind(), checkfirst=True)

    # Revert columns to their previous types if necessary (you can define the old types)
    # For example:
    # op.alter_column("ensid_screening_status", "overall_status", type_=sa.String())
    # Revert other columns similarly.
    