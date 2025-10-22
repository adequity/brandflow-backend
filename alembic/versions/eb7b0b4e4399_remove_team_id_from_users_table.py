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
    # team_id 컬럼 삭제 전 데이터 확인 및 로깅
    connection = op.get_bind()

    # 기존 team_id 값이 있는 사용자 확인
    result = connection.execute(sa.text("""
        SELECT id, name, email, role, team_id, team_name, team_leader_id
        FROM users
        WHERE team_id IS NOT NULL
    """))

    users_with_team_id = result.fetchall()
    if users_with_team_id:
        print(f"\n⚠️  {len(users_with_team_id)}명의 사용자가 team_id 값을 가지고 있습니다:")
        for user in users_with_team_id:
            print(f"  - ID: {user[0]}, 이름: {user[1]}, Role: {user[3]}, team_id: {user[4]}, team_name: {user[5]}, team_leader_id: {user[6]}")
        print("\n✅ team_leader_id가 이미 팀 식별자로 사용되므로 team_id는 안전하게 제거됩니다.\n")
    else:
        print("\n✅ team_id 값을 가진 사용자가 없습니다. 안전하게 컬럼을 제거합니다.\n")

    # team_id 컬럼 삭제 (team_leader_id가 이미 팀 식별자로 사용되므로 중복)
    op.drop_column('users', 'team_id')


def downgrade() -> None:
    # 롤백 시 team_id 컬럼 복원
    op.add_column('users', sa.Column('team_id', sa.Integer(), nullable=True))