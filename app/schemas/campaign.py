from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.models.campaign import CampaignStatus


class CampaignBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    client_company: str = Field(..., min_length=1, max_length=200)
    budget: float = Field(..., gt=0)
    start_date: datetime
    end_date: datetime


class CampaignCreate(CampaignBase):
    manager_id: Optional[int] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    client_company: Optional[str] = Field(None, min_length=1, max_length=200)
    budget: Optional[float] = Field(None, gt=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[CampaignStatus] = None


class CampaignResponse(CampaignBase):
    id: int
    status: CampaignStatus
    creator_id: int
    manager_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    # 관계 정보 (선택적)
    creator_name: Optional[str] = None
    manager_name: Optional[str] = None

    class Config:
        from_attributes = True