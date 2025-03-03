from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.sql import expression

# revision identifiers, used by Alembic.
revision = "4c9b4f28afca"
down_revision = "336536a9b257"
branch_labels = None
depends_on = None


# Define the finalstatus Enum for PostgreSQL
finalstatus_enum = ENUM('ACCEPTED', 'REJECTED', 'PENDING', name='finalstatus', create_type=False)

def upgrade():
    # Check if the column already exists before trying to add it
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT column_name
        FROM information_schema.columns 
        WHERE table_name = 'upload_supplier_master_data' AND column_name = 'final_status'
    """))
    
    if not result.fetchone():  # Column does not exist
        # Create the finalstatus enum type in PostgreSQL
        finalstatus_enum.create(op.get_bind(), checkfirst=True)
        
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
    # Drop the final_status column
    op.drop_column('upload_supplier_master_data', 'final_status')

    # Drop the finalstatus enum type if no longer needed
    finalstatus_enum.drop(op.get_bind(), checkfirst=True)