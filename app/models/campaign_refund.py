from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Numeric, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from .base import Base, TimestampMixin


class RefundType(str, enum.Enum):
    FULL = "전액환불"
    PARTIAL = "부분환불"


class RefundStatus(str, enum.Enum):
    PENDING = "환불대기"
    APPROVED = "환불승인"
    COMPLETED = "환불완료"
    REJECTED = "환불거절"


class CampaignRefund(Base, TimestampMixin):
    """캠페인 환불 기록 모델"""
    __tablename__ = "campaign_refunds"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)

    # 환불 정보
    refund_type = Column(SQLEnum(RefundType), nullable=False)
    refund_amount = Column(Numeric(12, 2), nullable=False)
    original_amount = Column(Numeric(12, 2), nullable=False)
    refund_reason = Column(Text, nullable=True)
    status = Column(SQLEnum(RefundStatus), default=RefundStatus.PENDING)

    # 처리자 정보
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # 취소 계산서 파일
    cancel_invoice_url = Column(String(500), nullable=True)
    cancel_invoice_name = Column(String(200), nullable=True)
    cancel_invoice_size = Column(Integer, nullable=True)

    # 관계 설정
    campaign = relationship("Campaign", back_populates="refunds")
    requester = relationship("User", foreign_keys=[requested_by])
    approver = relationship("User", foreign_keys=[approved_by])

    def __repr__(self):
        return f"<CampaignRefund(id={self.id}, campaign_id={self.campaign_id}, type={self.refund_type}, amount={self.refund_amount})>"
