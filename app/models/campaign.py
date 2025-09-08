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
    description = Column(Text, nullable=True)
    client_company = Column(String(200), nullable=False)
    budget = Column(Float, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.DRAFT)
    
    # 외래키
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 클라이언트 ID (선택적)
    
    # 관계 설정
    creator = relationship("User", foreign_keys=[creator_id], back_populates="campaigns")
    client = relationship("User", foreign_keys=[client_id])  # 클라이언트 관계
    purchase_requests = relationship("PurchaseRequest", back_populates="campaign")
    
    @property
    def creator_name(self) -> Optional[str]:
        """담당자 이름 반환"""
        if self.creator:
            return self.creator.name or f"{self.creator.first_name or ''} {self.creator.last_name or ''}".strip() or self.creator.username
        return None
    
    @property
    def client_name(self) -> Optional[str]:
        """클라이언트 이름 반환"""
        if self.client:
            return self.client.name or f"{self.client.first_name or ''} {self.client.last_name or ''}".strip() or self.client.username
        return self.client_company  # fallback to company name
    
    def __repr__(self):
        return f"<Campaign(id={self.id}, name={self.name}, status={self.status})>"