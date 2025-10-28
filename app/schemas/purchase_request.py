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
    resource_type: Optional[str] = Field(None, alias="resourceType")
    priority: Optional[str] = Field(default="보통")
    due_date: Optional[datetime] = Field(None, alias="dueDate")
    approver_comment: Optional[str] = Field(None, alias="approverComment")
    reject_reason: Optional[str] = Field(None, alias="rejectReason")

    class Config:
        populate_by_name = True  # alias와 실제 필드명 모두 허용


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
    resource_type: Optional[str] = Field(None, alias="resourceType")
    priority: Optional[str] = None
    due_date: Optional[datetime] = Field(None, alias="dueDate")
    approver_comment: Optional[str] = Field(None, alias="approverComment")
    reject_reason: Optional[str] = Field(None, alias="rejectReason")

    class Config:
        populate_by_name = True  # alias와 실제 필드명 모두 허용


class PurchaseRequestResponse(PurchaseRequestBase):
    id: int
    status: RequestStatus
    requester_id: int
    campaign_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True