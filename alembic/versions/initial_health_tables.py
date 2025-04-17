"""create health tables

Revision ID: 01
Create Date: 2023-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '01'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create health test results table
    op.create_table(
        'api_health_tests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_name', sa.String(length=100), nullable=False),
        sa.Column('test_name', sa.String(length=255), nullable=False),
        sa.Column('last_status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service_name', 'test_name', name='unique_service_test')
    )
    
    # Create index for faster queries
    op.create_index('idx_health_tests_service', 'api_health_tests', ['service_name'])
    op.create_index('idx_health_tests_updated', 'api_health_tests', ['updated_at'])
    
    # Create health checks summary table
    op.create_table(
        'api_health_checks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_name', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('last_successful_check', sa.DateTime(), nullable=True),
        sa.Column('total_tests', sa.Integer(), nullable=True),
        sa.Column('passing_tests', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service_name')
    )


def downgrade():
    op.drop_table('api_health_checks')
    op.drop_table('api_health_tests')