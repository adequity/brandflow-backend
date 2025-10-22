from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Enum as SQLEnum, Boolean, Numeric
from sqlalchemy.orm import relationship
import enum
from typing import Optional
from decimal import Decimal

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
    company = Column(String(200), nullable=True, index=True, default='default_company')  # 회사별 캠페인 분리
    budget = Column(Float, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.DRAFT)
    # executionStatus = Column(String(50), default="대기", nullable=True)  # 집행 상태 필드 - 임시 비활성화

    # 재무 관련 필드
    invoice_issued = Column(Boolean, default=False, nullable=True)  # 계산서 발행 완료
    payment_completed = Column(Boolean, default=False, nullable=True)  # 입금 완료

    # 카톡 관리 관련 필드
    chat_content = Column(Text, nullable=True)  # 카톡 대화 내용
    chat_summary = Column(Text, nullable=True)  # 카톡 요약 (주요 논의사항, 결정사항)
    chat_attachments = Column(Text, nullable=True)  # 첨부파일/링크 정보
    chat_images = Column(Text, nullable=True)  # 카톡 스크린샷 이미지 URL (JSON array 문자열)

    # 원가 및 이익 관련 필드
    cost = Column(Numeric(12, 2), default=0, nullable=True)  # 실제 원가
    margin = Column(Numeric(12, 2), default=0, nullable=True)  # 이익 (budget - cost)
    margin_rate = Column(Numeric(5, 2), default=0, nullable=True)  # 이익률 (%)
    estimated_cost = Column(Numeric(12, 2), default=0, nullable=True)  # 예상 원가

    # 일정 관련 필드
    invoice_due_date = Column(DateTime, nullable=True)  # 계산서 발행 마감일
    payment_due_date = Column(DateTime, nullable=True)  # 결제 마감일
    project_due_date = Column(DateTime, nullable=True)  # 프로젝트 완료 마감일
    
    # 외래키
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 클라이언트 사용자 ID
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 캠페인 담당 직원 ID
    
    # 관계 설정
    creator = relationship("User", back_populates="campaigns", foreign_keys=[creator_id])
    client_user = relationship("User", foreign_keys=[client_user_id], lazy="selectin")  # 클라이언트 사용자 관계 (eager loading)
    staff_user = relationship("User", foreign_keys=[staff_id], lazy="selectin")  # 담당 직원 관계 (eager loading)
    purchase_requests = relationship("PurchaseRequest", back_populates="campaign")
    posts = relationship("Post", back_populates="campaign", cascade="all, delete-orphan")
    # costs relationship은 campaign_costs 엔드포인트에서 직접 쿼리로 처리 (순환 import 방지)
    # costs = relationship("CampaignCost", back_populates="campaign", cascade="all, delete-orphan")
    
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