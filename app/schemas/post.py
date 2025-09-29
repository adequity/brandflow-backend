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
    start_date: Optional[str] = None  # 기존 호환성
    due_date: Optional[str] = None    # 기존 호환성
    start_datetime: Optional[datetime] = None  # 새로운 DateTime 필드
    due_datetime: Optional[datetime] = None    # 새로운 DateTime 필드
    product_id: Optional[int] = None
    quantity: Optional[int] = 1
    cost: Optional[float] = None  # 포스트별 작업 단가
    product_cost: Optional[float] = None  # 제품 단가 (원가)
    product_name: Optional[str] = None  # 제품명
    assigned_user_id: Optional[int] = None  # 포스트 담당자


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
    start_date: Optional[str] = None  # 기존 호환성
    due_date: Optional[str] = None    # 기존 호환성
    start_datetime: Optional[datetime] = None  # 새로운 DateTime 필드
    due_datetime: Optional[datetime] = None    # 새로운 DateTime 필드
    product_id: Optional[int] = None
    quantity: Optional[int] = None
    cost: Optional[float] = None  # 포스트별 작업 단가
    product_cost: Optional[float] = None  # 제품 단가 (원가)
    product_name: Optional[str] = None  # 제품명
    assigned_user_id: Optional[int] = None  # 포스트 담당자


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
    start_date: Optional[str]  # 기존 호환성
    due_date: Optional[str]    # 기존 호환성
    start_datetime: Optional[datetime] = None  # 새로운 DateTime 필드
    due_datetime: Optional[datetime] = None    # 새로운 DateTime 필드
    product_id: Optional[int]
    quantity: Optional[int]
    cost: Optional[float]  # 포스트별 작업 단가
    product_cost: Optional[float]  # 제품 단가 (원가)
    product_name: Optional[str]  # 제품명
    assigned_user_id: Optional[int]  # 포스트 담당자
    campaign_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True