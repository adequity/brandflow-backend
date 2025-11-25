"""add color column to work_types

Revision ID: 006_add_color_to_work_types
Revises: add_company_to_work_types
Create Date: 2025-01-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_add_color_to_work_types'
down_revision = 'add_company_to_work_types'  # 이전 마이그레이션
branch_labels = None
depends_on = None


def upgrade():
    # work_types 테이블에 color 컬럼 추가
    op.add_column('work_types', sa.Column('color', sa.String(7), nullable=True, server_default='#6B7280'))

    # 기존 데이터에 기본 색상 설정
    op.execute("UPDATE work_types SET color = '#6B7280' WHERE color IS NULL")


def downgrade():
    # work_types 테이블에서 color 컬럼 제거
    op.drop_column('work_types', 'color')
