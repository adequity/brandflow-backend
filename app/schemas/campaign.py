from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

from app.models.campaign import CampaignStatus


class CampaignBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None  # Add description field for frontend compatibility
    client_company: Optional[str] = Field(None, max_length=200)
    budget: Optional[float] = Field(None, ge=0)  # 0 이상 허용, 선택적
    staff_id: Optional[int] = None  # 캠페인 담당 직원 ID
    start_date: Optional[datetime] = None  # 선택적
    end_date: Optional[datetime] = None    # 선택적
    invoice_issued: Optional[bool] = None  # 계산서 발행 완료
    payment_completed: Optional[bool] = None  # 입금 완료
    invoice_due_date: Optional[datetime] = None  # 계산서 발행 마감일
    payment_due_date: Optional[datetime] = None  # 결제 마감일
    project_due_date: Optional[datetime] = None  # 프로젝트 완료 마감일
    # 원가 및 이익 관련 필드
    cost: Optional[float] = None  # 실제 원가
    margin: Optional[float] = None  # 이익
    margin_rate: Optional[float] = None  # 이익률
    estimated_cost: Optional[float] = None  # 예상 원가


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None  # Add description field for frontend compatibility
    client_company: Optional[str] = Field(None, min_length=1, max_length=200)
    budget: Optional[float] = Field(None, gt=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[CampaignStatus] = None
    invoice_issued: Optional[bool] = None  # 계산서 발행 완료
    payment_completed: Optional[bool] = None  # 입금 완료
    invoice_due_date: Optional[datetime] = None  # 계산서 발행 마감일
    payment_due_date: Optional[datetime] = None  # 결제 마감일
    project_due_date: Optional[datetime] = None  # 프로젝트 완료 마감일
    # creator_id는 기존 필드이므로 여기서 수정 가능하게 추가
    creator_id: Optional[int] = None
    staff_id: Optional[int] = None  # 캠페인 담당 직원 ID


class CampaignResponse(CampaignBase):
    id: int
    status: CampaignStatus
    creator_id: int
    client_user_id: Optional[int] = None  # 클라이언트 사용자 ID 추가
    staff_id: Optional[int] = None  # 캠페인 담당 직원 ID
    created_at: datetime
    updated_at: datetime

    # 관계 정보 (선택적)
    creator_name: Optional[str] = None
    client_name: Optional[str] = None
    client_user: Optional[Dict[str, Any]] = None  # 클라이언트 사용자 정보 추가

    class Config:
        from_attributes = True


class CampaignDuplicateRequest(BaseModel):
    """캠페인 복사 요청"""
    new_name: str = Field(..., min_length=2, max_length=200, description="새 캠페인명")
    start_date: datetime = Field(..., description="시작일")
    end_date: datetime = Field(..., description="종료일")
    staff_id: Optional[int] = Field(None, description="담당자 ID (미지정 시 현재 사용자)")
    budget: float = Field(..., ge=0, description="예산")


class CampaignDuplicateResponse(BaseModel):
    """캠페인 복사 응답"""
    success: bool
    message: str
    campaign: CampaignResponse