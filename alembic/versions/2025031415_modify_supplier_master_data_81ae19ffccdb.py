"""Modify supplier_master_data

Revision ID: 81ae19ffccdb
Revises: 50c9a414ea0f
Create Date: 2025-03-14 13:15:12.332370
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.sql import expression

# revision identifiers, used by Alembic.
revision = "81ae19ffccdb"
down_revision = "50c9a414ea0f"
branch_labels = None
depends_on = None

def upgrade():
    # Create ENUM type explicitly in PostgreSQL
    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'status') "
            "THEN CREATE TYPE status AS ENUM ('NOT_STARTED', 'STARTED', 'IN_PROGRESS', 'COMPLETED', 'FAILED'); END IF; END $$;"
        )
    )

    # Add the new column using the ENUM type
    op.add_column(
        "supplier_master_data",
        sa.Column(
            "report_generation_status",
            ENUM("NOT_STARTED", "STARTED", "IN_PROGRESS", "COMPLETED", "FAILED", name="status", create_type=False),
            server_default=expression.literal("NOT_STARTED"),
            nullable=False,
        ),
    )

def downgrade():
    # Drop the column
    op.drop_column("supplier_master_data", "report_generation_status")

    # Drop ENUM type only if no other columns depend on it
    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = 'status'::regtype) "
            "THEN DROP TYPE status; END IF; END $$;"
        )
    )
