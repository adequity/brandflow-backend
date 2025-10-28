from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, Enum as SQLEnum, Date
from sqlalchemy.orm import relationship
import enum

from .base import Base, TimestampMixin


class RequestStatus(str, enum.Enum):
    PENDING = "대기"
    APPROVED = "승인"
    REJECTED = "거절"
    COMPLETED = "완료"


class PurchaseRequest(Base, TimestampMixin):
    __tablename__ = "purchase_requests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=False)
    company = Column(String(200), nullable=True, index=True, default='default_company')  # 회사별 구매요청 분리
    quantity = Column(Integer, default=1)
    vendor = Column(String(200), nullable=True)
    resource_type = Column(String(100), nullable=True, index=True)  # 지출 카테고리 (기자재, 사무용품, 교통비 등)
    priority = Column(String(50), nullable=True, default='보통')  # 우선순위 (긴급, 높음, 보통, 낮음)
    due_date = Column(Date, nullable=True)  # 희망 완료일
    receipt_file_url = Column(String(500), nullable=True)  # 영수증 파일 URL (단일)
    attachment_urls = Column(Text, nullable=True)  # 첨부파일 URLs (JSON 배열 - 다중)
    status = Column(SQLEnum(RequestStatus), default=RequestStatus.PENDING)
    approver_comment = Column(Text, nullable=True)  # 승인자 코멘트
    reject_reason = Column(Text, nullable=True)  # 거절 사유
    
    # 외래키
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    
    # 관계 설정
    requester = relationship("User", back_populates="purchase_requests")
    campaign = relationship("Campaign", back_populates="purchase_requests")
    
    def __repr__(self):
        return f"<PurchaseRequest(id={self.id}, title={self.title}, amount={self.amount})>"