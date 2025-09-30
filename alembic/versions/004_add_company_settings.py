"""add_company_settings

Revision ID: 004
Revises: bbf3e8512c20
Create Date: 2025-09-30 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = 'bbf3e8512c20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Insert new company settings for bank account and seal image
    op.execute("""
        INSERT INTO system_settings (setting_key, setting_name, default_value, category, description, value_type) VALUES
        ('company_info_bank_name', '은행명', '', 'branding', '공급자 은행명', 'text'),
        ('company_info_account_number', '계좌번호', '', 'branding', '공급자 계좌번호', 'text'),
        ('company_info_account_holder', '예금주', '', 'branding', '공급자 계좌 예금주명', 'text'),
        ('company_info_seal_image_url', '도장 이미지 URL', '', 'branding', '공급자 도장 이미지 파일 URL', 'text')
        ON CONFLICT (setting_key) DO NOTHING;
    """)


def downgrade() -> None:
    # Remove company settings for bank account and seal image
    op.execute("""
        DELETE FROM system_settings WHERE setting_key IN (
            'company_info_bank_name',
            'company_info_account_number',
            'company_info_account_holder',
            'company_info_seal_image_url'
        );
    """)