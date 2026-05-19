from alembic import op
import sqlalchemy as sa

revision = '011'
down_revision = '010'

def upgrade():
    op.add_column('student_profiles', sa.Column('role', sa.String(50), server_default='student', nullable=False))

def downgrade():
    op.drop_column('student_profiles', 'role')
