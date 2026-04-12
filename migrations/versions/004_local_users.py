"""No-op — local users table not needed, Supabase Auth manages users.

Revision ID: 004
Revises: 003
Create Date: 2026-04-12
"""

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
