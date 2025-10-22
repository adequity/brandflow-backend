from sqlalchemy import Column, Integer, String, Date, Boolean, Numeric
from decimal import Decimal

from .base import Base, TimestampMixin


class IncentiveRule(Base, TimestampMixin):
    """인센티브 정책 규칙 모델"""
    __tablename__ = "incentive_rules"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(50), nullable=False, unique=True, index=True)  # 역할 (STAFF, TEAM_LEADER, AGENCY_ADMIN)

    # 기본 인센티브율 (%)
    personal_rate = Column(Numeric(5, 2), default=10.0, nullable=True)  # 본인 담당 이익 대비 인센티브율
    team_rate = Column(Numeric(5, 2), default=15.0, nullable=True)  # 팀 이익 대비 인센티브율 (TEAM_LEADER용)
    company_rate = Column(Numeric(5, 2), default=5.0, nullable=True)  # 회사 이익 대비 인센티브율 (AGENCY_ADMIN용)

    # 성과 보너스 기준
    bonus_threshold_margin = Column(Numeric(12, 2), nullable=True)  # 보너스 지급 기준 이익 금액
    bonus_amount = Column(Numeric(12, 2), nullable=True)  # 보너스 금액
    bonus_completion_rate = Column(Numeric(5, 2), nullable=True)  # 보너스 지급 기준 완료율 (%)

    # 활성화
    is_active = Column(Boolean, default=True, nullable=True)  # 정책 활성화 여부
    effective_from = Column(Date, nullable=True)  # 정책 적용 시작일

    def __repr__(self):
        return f"<IncentiveRule(id={self.id}, role={self.role}, personal_rate={self.personal_rate}%)>"
