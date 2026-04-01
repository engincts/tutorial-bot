"""Users table removed — Supabase Auth manages users.

Revision ID: 003
Revises: 002
Create Date: 2026-04-01
"""

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # Supabase Auth manages users — no local users table needed


def downgrade() -> None:
    pass
