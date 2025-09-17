"""add_published_url_to_posts

Revision ID: 002
Revises: 4d03a607265d
Create Date: 2025-09-17 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '4d03a607265d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add published_url column to posts table if it doesn't exist
    op.add_column('posts', sa.Column('published_url', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove published_url column from posts table
    op.drop_column('posts', 'published_url')