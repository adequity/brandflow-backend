from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from decimal import Decimal
import enum

from .base import Base, TimestampMixin


class IncentiveStatus(str, enum.Enum):
    """인센티브 상태"""
    DRAFT = "draft"  # 초안
    CONFIRMED = "confirmed"  # 확정
    PAID = "paid"  # 지급 완료


class Incentive(Base, TimestampMixin):
    """월간 인센티브 모델"""
    __tablename__ = "incentives"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)

    # 매출 데이터
    personal_revenue = Column(Numeric(12, 2), default=0, nullable=True)  # 본인 담당 매출
    team_revenue = Column(Numeric(12, 2), default=0, nullable=True)  # 팀 전체 매출
    company_revenue = Column(Numeric(12, 2), default=0, nullable=True)  # 회사 전체 매출

    # 원가 데이터
    personal_cost = Column(Numeric(12, 2), default=0, nullable=True)  # 본인 담당 원가
    team_cost = Column(Numeric(12, 2), default=0, nullable=True)  # 팀 전체 원가
    company_cost = Column(Numeric(12, 2), default=0, nullable=True)  # 회사 전체 원가

    # 이익 데이터 (margin = revenue - cost)
    personal_margin = Column(Numeric(12, 2), default=0, nullable=True)  # 본인 담당 이익
    team_margin = Column(Numeric(12, 2), default=0, nullable=True)  # 팀 전체 이익
    company_margin = Column(Numeric(12, 2), default=0, nullable=True)  # 회사 전체 이익

    # 마진율 (%)
    personal_margin_rate = Column(Numeric(5, 2), default=0, nullable=True)  # 본인 마진율
    team_margin_rate = Column(Numeric(5, 2), default=0, nullable=True)  # 팀 마진율
    company_margin_rate = Column(Numeric(5, 2), default=0, nullable=True)  # 회사 마진율

    # 인센티브 금액
    personal_incentive = Column(Numeric(12, 2), default=0, nullable=True)  # 본인 인센티브
    team_incentive = Column(Numeric(12, 2), default=0, nullable=True)  # 팀 인센티브 (TEAM_LEADER만)
    bonus = Column(Numeric(12, 2), default=0, nullable=True)  # 성과 보너스
    total_incentive = Column(Numeric(12, 2), default=0, nullable=True)  # 총 인센티브

    # 인센티브율
    personal_rate = Column(Numeric(5, 2), default=10.0, nullable=True)  # 본인 인센티브율 (%)
    team_rate = Column(Numeric(5, 2), default=15.0, nullable=True)  # 팀 인센티브율 (%)

    # 성과 지표
    campaign_count = Column(Integer, default=0, nullable=True)  # 담당 캠페인 수
    completed_campaign_count = Column(Integer, default=0, nullable=True)  # 완료 캠페인 수
    completion_rate = Column(Numeric(5, 2), default=0, nullable=True)  # 완료율 (%)

    # 상태
    status = Column(String(20), default=IncentiveStatus.DRAFT.value, nullable=True)
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 확정자 ID
    confirmed_at = Column(DateTime, nullable=True)  # 확정 일시
    paid_at = Column(DateTime, nullable=True)  # 지급 일시

    # 메타 정보
    notes = Column(Text, nullable=True)  # 비고

    # 관계 설정
    user = relationship("User", foreign_keys=[user_id])
    confirmer = relationship("User", foreign_keys=[confirmed_by])

    # 유니크 제약조건: 한 사용자의 특정 년월에 대한 인센티브는 하나만 존재
    __table_args__ = (
        UniqueConstraint('user_id', 'year', 'month', name='uq_incentives_user_year_month'),
    )

    def __repr__(self):
        return f"<Incentive(id={self.id}, user_id={self.user_id}, {self.year}-{self.month}, total={self.total_incentive})>"
