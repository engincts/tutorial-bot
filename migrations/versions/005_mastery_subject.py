"""Add subject column to mastery_scores

Revision ID: 005
Revises: 004
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mastery_scores",
        sa.Column("subject", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mastery_scores", "subject")
