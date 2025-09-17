"""add_financial_fields_to_campaigns

Revision ID: 4d03a607265d
Revises: 001
Create Date: 2025-09-17 17:15:49.511491

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d03a607265d'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add financial fields to campaigns table
    op.add_column('campaigns', sa.Column('invoice_issued', sa.Boolean(), nullable=True, default=False))
    op.add_column('campaigns', sa.Column('payment_completed', sa.Boolean(), nullable=True, default=False))


def downgrade() -> None:
    # Remove financial fields from campaigns table
    op.drop_column('campaigns', 'payment_completed')
    op.drop_column('campaigns', 'invoice_issued')