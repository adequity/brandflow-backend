from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Enum as SQLEnum
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
    client_company = Column(String(200), nullable=False)
    budget = Column(Float, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.DRAFT)
    
    # 외래키
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 관계 설정
    creator = relationship("User", back_populates="campaigns")
    purchase_requests = relationship("PurchaseRequest", back_populates="campaign")
    
    @property
    def description(self) -> str:
        """설명 필드 - DB에 없는 필드이므로 빈 문자열 반환"""
        return ""
    
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