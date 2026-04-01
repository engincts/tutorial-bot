"""Rename tables to clearer names.

Revision ID: 002
Revises: 001
Create Date: 2026-04-01
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("learner_profiles", "student_profiles")
    op.rename_table("kc_mastery", "mastery_scores")
    op.rename_table("misconceptions", "student_errors")
    op.rename_table("content_chunks", "curriculum_chunks")
    op.rename_table("interaction_embeddings", "chat_history")


def downgrade() -> None:
    op.rename_table("student_profiles", "learner_profiles")
    op.rename_table("mastery_scores", "kc_mastery")
    op.rename_table("student_errors", "misconceptions")
    op.rename_table("curriculum_chunks", "content_chunks")
    op.rename_table("chat_history", "interaction_embeddings")
