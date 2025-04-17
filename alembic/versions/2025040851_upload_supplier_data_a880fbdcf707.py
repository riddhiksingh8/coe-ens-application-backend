"""upload supplier data

Revision ID: a880fbdcf707
Revises: 19db905d25f1
Create Date: 2025-04-08 11:51:38.510610
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision = "a880fbdcf707"
down_revision = "19db905d25f1"
branch_labels = None
depends_on = None

# Define the new enum type with 'PENDING' added
new_enum_type = ENUM(
    "RETAIN",
    "REMOVE",
    "UNIQUE",
    name="dupinsession",
    create_type=False  # Create during upgrade
)


def upgrade():
    # Create ENUM type if not exists (PostgreSQL)
    new_enum_type.create(op.get_bind(), checkfirst=True)

    # Add duplicate_in_session column
    op.add_column(
        "upload_supplier_master_data",
        sa.Column(
            "duplicate_in_session",
            new_enum_type,
            nullable=False,
            server_default="RETAIN",  # default is RETAIN as per enum options
        ),
    )

    # Add start_date and end_date if not already exist
    conn = op.get_bind()

    for column_name in ["start_date", "end_date"]:
        result = conn.execute(
            sa.text(
                f"""
                SELECT 1
                FROM information_schema.columns 
                WHERE table_name='news_master' AND column_name='{column_name}'
                """
            )
        ).fetchone()

        if not result:
            op.add_column("news_master", sa.Column(column_name, sa.Date(), nullable=True))


def downgrade():
    # Drop added columns if they exist
    conn = op.get_bind()

    for column_name in ["start_date", "end_date"]:
        result = conn.execute(
            sa.text(
                f"""
                SELECT 1
                FROM information_schema.columns 
                WHERE table_name='news_master' AND column_name='{column_name}'
                """
            )
        ).fetchone()

        if result:
            op.drop_column("news_master", column_name)

    op.drop_column("upload_supplier_master_data", "duplicate_in_session")

    # Drop ENUM type
    new_enum_type.drop(op.get_bind(), checkfirst=True)
