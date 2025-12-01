"""add product_name to posts

Revision ID: 20251201_add_product_name
Revises: 20251030_defaults
Create Date: 2025-12-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251201_add_product_name'
down_revision = '20251030_defaults'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    posts 테이블에 product_name 컬럼 추가
    """
    # product_name 컬럼이 존재하지 않는 경우에만 추가
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'posts' AND column_name = 'product_name'
            ) THEN
                ALTER TABLE posts ADD COLUMN product_name VARCHAR(200);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """
    posts 테이블에서 product_name 컬럼 제거
    """
    op.drop_column('posts', 'product_name')
