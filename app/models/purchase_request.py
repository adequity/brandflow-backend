from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, Enum as SQLEnum
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
    status = Column(SQLEnum(RequestStatus), default=RequestStatus.PENDING)
    
    # 외래키
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    
    # 관계 설정
    requester = relationship("User", back_populates="purchase_requests")
    campaign = relationship("Campaign", back_populates="purchase_requests")
    
    def __repr__(self):
        return f"<PurchaseRequest(id={self.id}, title={self.title}, amount={self.amount})>"