from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class CompanySettings(Base, TimestampMixin):
    """회사별 설정 모델 - 각 회사(company)마다 독립적인 설정을 관리"""
    __tablename__ = "company_settings"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(200), nullable=False, index=True)  # User.company와 연결
    setting_key = Column(String(100), nullable=False, index=True)
    setting_value = Column(Text, nullable=True)

    # 수정자 정보
    modified_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # 관계
    modifier = relationship("User", foreign_keys=[modified_by])

    def __repr__(self):
        return f"<CompanySettings(company={self.company}, key={self.setting_key}, value={self.setting_value})>"


class CompanyInfo:
    """회사 정보를 담는 헬퍼 클래스"""

    def __init__(self, company: str, settings: dict = None):
        self.company = company
        self.settings = settings or {}

    @property
    def business_number(self) -> str:
        return self.settings.get("business_number", "")

    @property
    def company_name(self) -> str:
        return self.settings.get("company_name", "")

    @property
    def ceo_name(self) -> str:
        return self.settings.get("ceo_name", "")

    @property
    def company_address(self) -> str:
        return self.settings.get("company_address", "")

    @property
    def business_type(self) -> str:
        return self.settings.get("business_type", "")

    @property
    def business_item(self) -> str:
        return self.settings.get("business_item", "")

    @property
    def bank_name(self) -> str:
        return self.settings.get("bank_name", "")

    @property
    def account_number(self) -> str:
        return self.settings.get("account_number", "")

    @property
    def account_holder(self) -> str:
        return self.settings.get("account_holder", "")

    @property
    def seal_image_url(self) -> str:
        return self.settings.get("seal_image_url", "")

    def to_dict(self) -> dict:
        """DocumentTemplateBuilder에서 사용할 수 있는 형태로 변환"""
        return {
            "businessNumber": self.business_number,
            "name": self.company_name,
            "ceo": self.ceo_name,
            "address": self.company_address,
            "businessType": self.business_type,
            "businessItem": self.business_item,
            "bankName": self.bank_name,
            "accountNumber": self.account_number,
            "accountHolder": self.account_holder,
            "sealImageUrl": self.seal_image_url
        }