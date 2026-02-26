from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Numeric, String, Enum as SQLEnum
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin
from .campaign_refund import RefundType, RefundStatus


class PostRefund(Base, TimestampMixin):
    """업무(Post) 환불 기록 모델"""
    __tablename__ = "post_refunds"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)

    # 환불 정보
    refund_type = Column(SQLEnum(RefundType), nullable=False)
    refund_amount = Column(Numeric(12, 2), nullable=False)
    original_budget = Column(Numeric(12, 2), nullable=False)
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
    post = relationship("Post", back_populates="refunds")
    campaign = relationship("Campaign")
    requester = relationship("User", foreign_keys=[requested_by])
    approver = relationship("User", foreign_keys=[approved_by])

    def __repr__(self):
        return f"<PostRefund(id={self.id}, post_id={self.post_id}, type={self.refund_type}, amount={self.refund_amount})>"
