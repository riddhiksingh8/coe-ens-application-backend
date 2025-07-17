"""Update ens_continuous_group_mapping with ens_id, status, group_id

Revision ID: 8b4fe7fa8e93
Revises: 4ae827539a0c
Create Date: 2025-07-15 11:29:22.210728
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "8b4fe7fa8e93"
down_revision = "4ae827539a0c"
branch_labels = None
depends_on = None

source_enum = postgresql.ENUM('NEW_SESSION', 'OD', 'CM', 'PD', name='sourceenum', create_type=False)


def upgrade():
    source_enum.create(op.get_bind(), checkfirst=True)

    # Create new tables
    op.create_table(
        'continuous_monitoring',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('group_id', sa.String(), nullable=False, unique=True),
        sa.Column('group_name', sa.String())
    )

    op.create_table(
        'schedule_monitoring',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('group_id', sa.String(), nullable=False, unique=True),
        sa.Column('group_name', sa.String()),
        sa.Column('periodicity', sa.String()),
        sa.Column('start_date', sa.Date()),
        sa.Column('last_scheduled_date', sa.Date()),
        sa.Column('status', sa.String()),
        sa.Column('group_description', sa.Text()),
        sa.Column('created_by', sa.String())
    )

    op.create_table(
        'ens_schedule_group_mapping',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('ens_id', sa.String(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False)
    )

    op.create_table(
        'session_group_mapping',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String()),
        sa.Column('group_id', sa.String()),
        sa.Column('source_id', sa.String())
    )

    op.create_table(
        'ens_continuous_group_mapping',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('ens_id', sa.String(length=50), nullable=False),
        sa.Column('group_id', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True)
    )

    # Modify session_screening_status
    op.add_column('session_screening_status', sa.Column('source_id', sa.String(), nullable=True))
    op.add_column('session_screening_status', sa.Column('source', source_enum, nullable=True))

    # Modify entity_universe
    op.add_column('entity_universe', sa.Column('unmodified_name', sa.String(length=255), nullable=True))
    op.add_column('entity_universe', sa.Column('unmodified_name_international', sa.String(length=255), nullable=True))
    op.add_column('entity_universe', sa.Column('unmodified_address', sa.Text(), nullable=True))
    op.add_column('entity_universe', sa.Column('unmodified_postcode', sa.String(length=20), nullable=True))
    op.add_column('entity_universe', sa.Column('unmodified_city', sa.String(length=100), nullable=True))
    op.add_column('entity_universe', sa.Column('unmodified_country', sa.String(length=100), nullable=True))
    op.add_column('entity_universe', sa.Column('unmodified_phone_or_fax', sa.String(length=50), nullable=True))
    op.add_column('entity_universe', sa.Column('unmodified_email_or_website', sa.String(length=100), nullable=True))
    op.add_column('entity_universe', sa.Column('unmodified_national_id', sa.String(length=50), nullable=True))
    op.add_column('entity_universe', sa.Column('unmodified_state', sa.String(length=100), nullable=True))
    op.add_column('entity_universe', sa.Column('unmodified_address_type', sa.String(length=50), nullable=True))


def downgrade():
    # Drop columns from entity_universe
    op.drop_column('entity_universe', 'unmodified_address_type')
    op.drop_column('entity_universe', 'unmodified_state')
    op.drop_column('entity_universe', 'unmodified_national_id')
    op.drop_column('entity_universe', 'unmodified_email_or_website')
    op.drop_column('entity_universe', 'unmodified_phone_or_fax')
    op.drop_column('entity_universe', 'unmodified_country')
    op.drop_column('entity_universe', 'unmodified_city')
    op.drop_column('entity_universe', 'unmodified_postcode')
    op.drop_column('entity_universe', 'unmodified_address')
    op.drop_column('entity_universe', 'unmodified_name_international')
    op.drop_column('entity_universe', 'unmodified_name')
    op.drop_column('entity_universe', 'management')

    # Drop columns from session_screening_status
    op.drop_column('session_screening_status', 'source')
    op.drop_column('session_screening_status', 'source_id')

    # Drop newly created tables
    op.drop_table('ens_continuous_group_mapping')
    op.drop_table('session_group_mapping')
    op.drop_table('ens_schedule_group_mapping')
    op.drop_table('schedule_monitoring')
    op.drop_table('continuous_monitoring')

    # Drop ENUM type
    source_enum.drop(op.get_bind(), checkfirst=True)
