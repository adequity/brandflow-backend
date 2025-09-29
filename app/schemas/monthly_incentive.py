from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

from app.models.monthly_incentive import IncentiveStatus


class MonthlyIncentiveBase(BaseModel):
    user_id: int
    year: int = Field(..., ge=2020, le=2030)
    month: int = Field(..., ge=1, le=12)
    company: Optional[str] = None
    total_revenue: float = 0.0
    total_profit: float = 0.0
    campaign_count: int = 0
    incentive_rate: float = Field(..., ge=0.0, le=100.0)
    base_incentive_amount: float = 0.0
    profit_incentive_amount: float = 0.0
    adjustment_amount: float = 0.0
    bonus_amount: float = 0.0
    final_incentive_amount: float = 0.0
    status: IncentiveStatus = IncentiveStatus.CALCULATED
    notes: Optional[str] = None
    adjustment_reason: Optional[str] = None


class MonthlyIncentiveCreate(MonthlyIncentiveBase):
    pass


class MonthlyIncentiveUpdate(BaseModel):
    adjustment_amount: Optional[float] = None
    bonus_amount: Optional[float] = None
    status: Optional[IncentiveStatus] = None
    notes: Optional[str] = None
    adjustment_reason: Optional[str] = None
    approved_by: Optional[int] = None
    approved_at: Optional[str] = None
    paid_at: Optional[str] = None


class MonthlyIncentiveResponse(MonthlyIncentiveBase):
    id: int
    approved_by: Optional[int] = None
    approved_at: Optional[str] = None
    paid_at: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # 관계 정보 (선택적)
    user: Optional[Dict[str, Any]] = None
    approver: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class IncentiveCalculationRequest(BaseModel):
    year: int = Field(..., ge=2020, le=2030)
    month: int = Field(..., ge=1, le=12)
    company: Optional[str] = None  # 특정 회사만 계산할 경우
    recalculate: bool = False     # 기존 데이터 재계산 여부


class IncentiveCalculationResult(BaseModel):
    user_id: int
    user_name: str
    company: str
    status: str  # 'created', 'updated', 'skipped', 'error'
    message: str
    incentive_amount: float = 0.0


class IncentiveCalculationResponse(BaseModel):
    success: bool
    total_processed: int
    results: list[IncentiveCalculationResult]
    summary: Dict[str, int]  # {'created': 5, 'updated': 2, 'skipped': 3, 'error': 1}


class IncentiveStatsResponse(BaseModel):
    total_employees: int
    pending_incentives: int
    approved_incentives: int
    paid_incentives: int
    total_incentive_amount: float
    total_adjustment_amount: float
    total_bonus_amount: float
    total_final_amount: float
    companies: list[str]  # 포함된 회사 목록


class IncentiveListQuery(BaseModel):
    year: Optional[int] = None
    month: Optional[int] = None
    company: Optional[str] = None
    status: Optional[IncentiveStatus] = None
    user_id: Optional[int] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)