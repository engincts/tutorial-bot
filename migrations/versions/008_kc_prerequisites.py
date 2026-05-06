"""Add kc_prerequisites table

Revision ID: 008
Revises: 007
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "kc_prerequisites",
        sa.Column("kc_id", sa.String(255), primary_key=True),
        sa.Column("prereq_kc_id", sa.String(255), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

def downgrade() -> None:
    op.drop_table("kc_prerequisites")
