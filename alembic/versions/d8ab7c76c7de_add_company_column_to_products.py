"""add_company_column_to_products

Revision ID: d8ab7c76c7de
Revises: 005
Create Date: 2025-10-02 23:29:28.652675

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8ab7c76c7de'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add company column to products table
    op.add_column('products', sa.Column('company', sa.String(200), nullable=True, default='default_company'))

    # Create index on company column for better performance
    op.create_index(op.f('ix_products_company'), 'products', ['company'], unique=False)

    # Update existing products to have default_company value
    op.execute("UPDATE products SET company = 'default_company' WHERE company IS NULL")


def downgrade() -> None:
    # Remove index first
    op.drop_index(op.f('ix_products_company'), table_name='products')

    # Remove company column
    op.drop_column('products', 'company')