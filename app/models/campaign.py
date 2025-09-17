from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
import enum
from typing import Optional

from .base import Base, TimestampMixin


class CampaignStatus(str, enum.Enum):
    DRAFT = "초안"
    ACTIVE = "진행중"
    COMPLETED = "완료"
    CANCELLED = "취소"


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)  # Add description field for frontend compatibility
    client_company = Column(String(200), nullable=True)  # 기존 호환성 유지 (nullable로 변경)
    budget = Column(Float, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.DRAFT)
    # executionStatus = Column(String(50), default="대기", nullable=True)  # 집행 상태 필드 - 임시 비활성화

    # 재무 관련 필드
    invoice_issued = Column(Boolean, default=False, nullable=True)  # 계산서 발행 완료
    payment_completed = Column(Boolean, default=False, nullable=True)  # 입금 완료
    
    # 외래키
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 클라이언트 사용자 ID
    
    # 관계 설정
    creator = relationship("User", back_populates="campaigns", foreign_keys=[creator_id])
    client_user = relationship("User", foreign_keys=[client_user_id])  # 클라이언트 사용자 관계
    purchase_requests = relationship("PurchaseRequest", back_populates="campaign")
    posts = relationship("Post", back_populates="campaign")
    
    @property
    def creator_name(self) -> Optional[str]:
        """담당자 이름 반환"""
        if self.creator:
            return self.creator.name
        return None
    
    @property
    def client_name(self) -> Optional[str]:
        """클라이언트 이름 반환"""
        return self.client_company  # 기존 client_company 필드 사용
    
    def __repr__(self):
        return f"<Campaign(id={self.id}, name={self.name}, status={self.status})>"