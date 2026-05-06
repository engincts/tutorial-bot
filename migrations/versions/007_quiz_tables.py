"""Add quiz tables

Revision ID: 007
Revises: 006
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # ── quiz_sessions ─────────────────────────────────────────────
    op.create_table(
        "quiz_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kc_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["learner_id"], ["student_profiles.id"]),
    )

    # ── quiz_questions ────────────────────────────────────────────
    op.create_table(
        "quiz_questions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("quiz_id", UUID(as_uuid=True), nullable=False),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("options", sa.Text, nullable=True),  # JSON list
        sa.Column("correct_answer", sa.Text, nullable=False),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(["quiz_id"], ["quiz_sessions.id"]),
    )

    # ── quiz_answers ──────────────────────────────────────────────
    op.create_table(
        "quiz_answers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("quiz_id", UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", UUID(as_uuid=True), nullable=False),
        sa.Column("learner_answer", sa.Text, nullable=False),
        sa.Column("is_correct", sa.Boolean, nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["quiz_id"], ["quiz_sessions.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["quiz_questions.id"]),
    )

def downgrade() -> None:
    op.drop_table("quiz_answers")
    op.drop_table("quiz_questions")
    op.drop_table("quiz_sessions")
