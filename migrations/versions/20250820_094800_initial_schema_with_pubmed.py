"""Initial schema with PubMed documents, sync watermarks, and corpus checkpoints

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-08-20 09:48:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial schema."""
    # Create pubmed_documents table
    op.create_table(
        'pubmed_documents',
        sa.Column('pmid', sa.String(50), nullable=False),
        sa.Column('title', sa.String(1000), nullable=False),
        sa.Column('abstract', sa.Text(), nullable=True),
        sa.Column('authors', JSON(), nullable=True, default=sa.text("'[]'::json")),
        sa.Column('publication_date', sa.Date(), nullable=True),
        sa.Column('journal', sa.String(500), nullable=True),
        sa.Column('doi', sa.String(200), nullable=True),
        sa.Column('keywords', JSON(), nullable=True, default=sa.text("'[]'::json")),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('pmid')
    )

    # Create sync_watermarks table
    op.create_table(
        'sync_watermarks',
        sa.Column('query_key', sa.String(255), nullable=False),
        sa.Column('last_edat', sa.String(10), nullable=True),
        sa.Column('total_synced', sa.String(20), nullable=False, server_default='0'),
        sa.Column('last_sync_count', sa.String(20), nullable=False, server_default='0'),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('query_key')
    )

    # Create corpus_checkpoints table
    op.create_table(
        'corpus_checkpoints',
        sa.Column('checkpoint_id', sa.String(255), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('document_count', sa.String(20), nullable=False, server_default='0'),
        sa.Column('last_sync_edat', sa.String(10), nullable=True),
        sa.Column('primary_queries', JSON(), nullable=True, default=sa.text("'[]'::json")),
        sa.Column('sync_watermarks', JSON(), nullable=True, default=sa.text("'{}'::json")),
        sa.Column('total_documents', sa.String(20), nullable=False, server_default='0'),
        sa.Column('total_vectors', sa.String(20), nullable=False, server_default='0'),
        sa.Column('version', sa.String(50), nullable=False, server_default='1.0'),
        sa.Column('parent_checkpoint_id', sa.String(255), nullable=True),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('checkpoint_id')
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('corpus_checkpoints')
    op.drop_table('sync_watermarks')
    op.drop_table('pubmed_documents')