"""add priority, due_date, approver_comment, reject_reason to purchase_requests

Revision ID: 20251028_purchase
Revises: eb7b0b4e4399
Create Date: 2025-10-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251028_purchase'
down_revision = 'eb7b0b4e4399'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # purchase_requests 테이블에 새 컬럼 추가
    # 컬럼이 이미 존재하면 건너뛰기
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('purchase_requests')]

    if 'priority' not in columns:
        op.add_column('purchase_requests', sa.Column('priority', sa.String(length=50), nullable=True, server_default='보통'))

    if 'due_date' not in columns:
        op.add_column('purchase_requests', sa.Column('due_date', sa.Date(), nullable=True))

    if 'approver_comment' not in columns:
        op.add_column('purchase_requests', sa.Column('approver_comment', sa.Text(), nullable=True))

    if 'reject_reason' not in columns:
        op.add_column('purchase_requests', sa.Column('reject_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    # 롤백 시 컬럼 제거
    op.drop_column('purchase_requests', 'reject_reason')
    op.drop_column('purchase_requests', 'approver_comment')
    op.drop_column('purchase_requests', 'due_date')
    op.drop_column('purchase_requests', 'priority')
