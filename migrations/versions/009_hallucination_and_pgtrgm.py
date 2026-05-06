"""Add pg_trgm and hallucination logs

Revision ID: 009
Revises: 008
Create Date: 2026-05-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. pg_trgm extension
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')
    
    # 2. Add trigram index to curriculum_chunks content
    op.execute('CREATE INDEX IF NOT EXISTS trgm_idx_curriculum_chunks_content ON curriculum_chunks USING gin (content gin_trgm_ops);')

    # 3. Create hallucination_logs table
    op.create_table(
        'hallucination_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('learner_id', UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', UUID(as_uuid=True), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('assistant_response', sa.Text(), nullable=False),
        sa.Column('context_used', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

def downgrade() -> None:
    op.drop_table('hallucination_logs')
    op.execute('DROP INDEX IF EXISTS trgm_idx_curriculum_chunks_content;')
    op.execute('DROP EXTENSION IF EXISTS pg_trgm;')
