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
    pass


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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True