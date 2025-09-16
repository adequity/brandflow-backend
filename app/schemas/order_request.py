from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class OrderRequestCreate(BaseModel):
    title: str
    description: Optional[str] = None
    cost_price: Optional[int] = None
    resource_type: Optional[str] = None
    post_id: int


class OrderRequestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    cost_price: Optional[int] = None
    resource_type: Optional[str] = None


class OrderRequestResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    cost_price: Optional[int]
    resource_type: Optional[str]
    post_id: int
    user_id: int
    campaign_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True