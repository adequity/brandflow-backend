from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.models.campaign import CampaignStatus


class CampaignBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None  # Add description field for frontend compatibility
    client_company: Optional[str] = Field(None, max_length=200)
    budget: Optional[float] = Field(None, ge=0)  # 0 이상 허용, 선택적
    start_date: Optional[datetime] = None  # 선택적
    end_date: Optional[datetime] = None    # 선택적


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
    executionStatus: Optional[str] = None  # Add executionStatus field for frontend compatibility
    # creator_id는 기존 필드이므로 여기서 수정 가능하게 추가
    creator_id: Optional[int] = None


class CampaignResponse(CampaignBase):
    id: int
    status: CampaignStatus
    executionStatus: Optional[str] = None  # Add executionStatus field for frontend compatibility
    creator_id: int
    created_at: datetime
    updated_at: datetime

    # 관계 정보 (선택적)
    creator_name: Optional[str] = None
    client_name: Optional[str] = None

    class Config:
        from_attributes = True