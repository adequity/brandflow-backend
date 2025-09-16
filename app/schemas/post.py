from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PostCreate(BaseModel):
    title: str
    work_type: str = "블로그"
    topic_status: str = "대기"
    outline: Optional[str] = None
    outline_status: Optional[str] = None
    images: Optional[List[str]] = []
    published_url: Optional[str] = None
    order_request_status: Optional[str] = None
    order_request_id: Optional[int] = None
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    product_id: Optional[int] = None
    quantity: Optional[int] = 1


class PostUpdate(BaseModel):
    title: Optional[str] = None
    work_type: Optional[str] = None
    topic_status: Optional[str] = None
    outline: Optional[str] = None
    outline_status: Optional[str] = None
    images: Optional[List[str]] = None
    published_url: Optional[str] = None
    order_request_status: Optional[str] = None
    order_request_id: Optional[int] = None
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    product_id: Optional[int] = None
    quantity: Optional[int] = None


class PostResponse(BaseModel):
    id: int
    title: str
    work_type: str
    topic_status: str
    outline: Optional[str]
    outline_status: Optional[str]
    images: Optional[List[str]]
    published_url: Optional[str]
    order_request_status: Optional[str]
    order_request_id: Optional[int]
    start_date: Optional[str]
    due_date: Optional[str]
    product_id: Optional[int]
    quantity: Optional[int]
    campaign_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True