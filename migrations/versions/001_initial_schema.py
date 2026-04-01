"""Initial schema: pgvector extension + core tables

Revision ID: 001
Revises:
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    # pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── learner_profiles ─────────────────────────────────────────────
    op.create_table(
        "learner_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("preferred_language", sa.String(10), server_default="tr"),
        sa.Column("preferences", sa.Text, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            onupdate=sa.text("NOW()"),
        ),
    )

    # ── kc_mastery ───────────────────────────────────────────────────
    op.create_table(
        "kc_mastery",
        sa.Column("learner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kc_id", sa.String(255), nullable=False),
        sa.Column("p_mastery", sa.Float, server_default="0.3"),
        sa.Column("attempts", sa.Integer, server_default="0"),
        sa.Column(
            "last_interaction",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("learner_id", "kc_id"),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_profiles.id"]),
    )

    # ── content_chunks ───────────────────────────────────────────────
    op.create_table(
        "content_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.String(255), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("kc_tags", ARRAY(sa.String), server_default="{}"),
        sa.Column("metadata", sa.Text, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_content_chunks_document_id", "content_chunks", ["document_id"])

    # ── interaction_embeddings ───────────────────────────────────────
    op.create_table(
        "interaction_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("interaction_type", sa.String(50), nullable=False),
        sa.Column("content_summary", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("kc_tags", ARRAY(sa.String), server_default="{}"),
        sa.Column("correctness", sa.Boolean, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_profiles.id"]),
    )
    op.create_index(
        "ix_interaction_embeddings_learner_id",
        "interaction_embeddings",
        ["learner_id"],
    )

    # ── misconceptions ───────────────────────────────────────────────
    op.create_table(
        "misconceptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kc_id", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("resolved", sa.Boolean, server_default="false"),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_profiles.id"]),
    )

    # HNSW index'leri (pgvector 0.5+)
    op.execute("""
        CREATE INDEX ix_content_chunks_embedding_hnsw
        ON content_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX ix_interaction_embeddings_hnsw
        ON interaction_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.drop_table("misconceptions")
    op.drop_table("interaction_embeddings")
    op.drop_table("content_chunks")
    op.drop_table("kc_mastery")
    op.drop_table("learner_profiles")
    op.execute("DROP EXTENSION IF EXISTS vector")
