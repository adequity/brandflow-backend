"""remove team_id from users table

Revision ID: eb7b0b4e4399
Revises: d8ab7c76c7de
Create Date: 2025-10-22 22:43:16.060533

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb7b0b4e4399'
down_revision = 'd8ab7c76c7de'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # team_id 컬럼 삭제 (team_leader_id가 이미 팀 식별자로 사용되므로 중복)
    op.drop_column('users', 'team_id')


def downgrade() -> None:
    # 롤백 시 team_id 컬럼 복원
    op.add_column('users', sa.Column('team_id', sa.Integer(), nullable=True))