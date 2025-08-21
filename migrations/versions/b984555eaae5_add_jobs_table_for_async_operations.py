"""add_jobs_table_for_async_operations

Revision ID: b984555eaae5
Revises: 001_initial_schema
Create Date: 2025-08-21 12:41:13.566268

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b984555eaae5'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add jobs table for async operations."""
    # Create JobStatus enum
    job_status_enum = postgresql.ENUM('pending', 'running', 'completed', 'failed', 'cancelled', name='jobstatus')
    job_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create jobs table
    op.create_table('jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tool_name', sa.String(length=100), nullable=False),
        sa.Column('status', job_status_enum, nullable=False, server_default='pending'),
        sa.Column('trace_id', sa.String(length=36), nullable=False),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index(op.f('ix_jobs_created_at'), 'jobs', ['created_at'], unique=False)
    op.create_index(op.f('ix_jobs_expires_at'), 'jobs', ['expires_at'], unique=False)
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)
    op.create_index(op.f('ix_jobs_tool_name'), 'jobs', ['tool_name'], unique=False)
    op.create_index(op.f('ix_jobs_trace_id'), 'jobs', ['trace_id'], unique=False)


def downgrade() -> None:
    """Remove jobs table and enum."""
    # Drop indexes
    op.drop_index(op.f('ix_jobs_trace_id'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_tool_name'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_status'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_expires_at'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_created_at'), table_name='jobs')
    
    # Drop table
    op.drop_table('jobs')
    
    # Drop enum
    job_status_enum = postgresql.ENUM('pending', 'running', 'completed', 'failed', 'cancelled', name='jobstatus')
    job_status_enum.drop(op.get_bind(), checkfirst=True)