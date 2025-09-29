from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
import enum

from .base import Base, TimestampMixin


class IncentiveStatus(str, enum.Enum):
    CALCULATED = "계산완료"        # 계산 완료, 검토 대기
    PENDING = "검토대기"           # 관리자 검토 대기
    APPROVED = "승인완료"          # 승인 완료, 지급 대기
    PAID = "지급완료"             # 지급 완료
    ON_HOLD = "보류"              # 보류 상태
    CANCELLED = "취소"            # 취소 상태


class MonthlyIncentive(Base, TimestampMixin):
    __tablename__ = "monthly_incentives"

    id = Column(Integer, primary_key=True, index=True)

    # 기본 정보
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)

    # 회사 정보 (비정규화 - 히스토리 보존을 위해)
    company = Column(String(200), nullable=True)

    # 매출/수익 정보
    total_revenue = Column(Float, default=0.0)          # 총 매출
    total_profit = Column(Float, default=0.0)           # 총 이익 (매출 - 원가)
    campaign_count = Column(Integer, default=0)         # 완료 캠페인 수

    # 인센티브 계산
    incentive_rate = Column(Float, nullable=False)       # 계산 당시 인센티브율
    base_incentive_amount = Column(Float, default=0.0)   # 기본 인센티브 (매출 기준)
    profit_incentive_amount = Column(Float, default=0.0) # 이익 기준 인센티브
    adjustment_amount = Column(Float, default=0.0)       # 수동 조정 금액
    bonus_amount = Column(Float, default=0.0)            # 보너스 금액

    # 최종 금액
    final_incentive_amount = Column(Float, default=0.0)  # 최종 인센티브 금액

    # 상태 및 메모
    status = Column(SQLEnum(IncentiveStatus), default=IncentiveStatus.CALCULATED)
    notes = Column(Text, nullable=True)                  # 계산 근거, 조정 사유 등
    adjustment_reason = Column(Text, nullable=True)      # 조정 사유

    # 승인 관련
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 승인자
    approved_at = Column(String(50), nullable=True)      # 승인 일시 (ISO string)
    paid_at = Column(String(50), nullable=True)          # 지급 일시 (ISO string)

    # 관계 설정
    user = relationship("User", foreign_keys=[user_id], back_populates="monthly_incentives")
    approver = relationship("User", foreign_keys=[approved_by])

    # 복합 인덱스 (유니크 제약)
    __table_args__ = (
        Index('idx_user_year_month', 'user_id', 'year', 'month', unique=True),
        Index('idx_company_year_month', 'company', 'year', 'month'),
        Index('idx_status', 'status'),
    )

    def calculate_final_amount(self):
        """최종 인센티브 금액 계산"""
        self.final_incentive_amount = (
            self.base_incentive_amount +
            self.profit_incentive_amount +
            self.adjustment_amount +
            self.bonus_amount
        )
        return self.final_incentive_amount

    def __repr__(self):
        return f"<MonthlyIncentive(user_id={self.user_id}, {self.year}-{self.month:02d}, {self.final_incentive_amount})>"