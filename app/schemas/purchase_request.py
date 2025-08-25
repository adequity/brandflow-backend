from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.models.purchase_request import RequestStatus


class PurchaseRequestBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    amount: float = Field(..., gt=0)
    quantity: int = Field(default=1, gt=0)
    vendor: Optional[str] = Field(None, max_length=200)


class PurchaseRequestCreate(PurchaseRequestBase):
    campaign_id: Optional[int] = None


class PurchaseRequestUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    quantity: Optional[int] = Field(None, gt=0)
    vendor: Optional[str] = Field(None, max_length=200)
    status: Optional[RequestStatus] = None
    campaign_id: Optional[int] = None


class PurchaseRequestResponse(PurchaseRequestBase):
    id: int
    status: RequestStatus
    requester_id: int
    campaign_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True