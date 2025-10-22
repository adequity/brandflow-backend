from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Numeric
from sqlalchemy.orm import relationship
from decimal import Decimal

from .base import Base, TimestampMixin


class CampaignCost(Base, TimestampMixin):
    """캠페인 원가 항목 모델"""
    __tablename__ = "campaign_costs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)

    # 원가 정보
    cost_type = Column(String(50), nullable=False, index=True)  # 원가 유형 (광고비, 인건비, 외주비 등)
    description = Column(Text, nullable=True)  # 상세 설명
    amount = Column(Numeric(12, 2), nullable=False)  # 금액

    # 증빙 정보
    receipt_url = Column(Text, nullable=True)  # 영수증/증빙 파일 URL
    vendor_name = Column(String(200), nullable=True)  # 공급업체명

    # 승인 워크플로우
    is_approved = Column(Boolean, default=False, nullable=True)  # 승인 여부
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 승인자 ID
    approved_at = Column(DateTime, nullable=True)  # 승인 일시

    # 생성 정보
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 생성자 ID

    # 관계 설정
    # Campaign 모델에서 costs relationship이 주석 처리되어 있으므로 back_populates 제거
    campaign = relationship("Campaign", foreign_keys=[campaign_id])
    approver = relationship("User", foreign_keys=[approved_by])
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<CampaignCost(id={self.id}, campaign_id={self.campaign_id}, type={self.cost_type}, amount={self.amount})>"
