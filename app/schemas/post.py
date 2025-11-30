from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class PostCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    title: str
    work_type: str = Field(default="블로그", alias="workType")
    topic_status: str = Field(default="주제 승인 대기", alias="topicStatus")
    outline: Optional[str] = None
    outline_status: Optional[str] = Field(None, alias="outlineStatus")
    images: Optional[List[str]] = []
    published_url: Optional[str] = Field(None, alias="publishedUrl")
    order_request_status: Optional[str] = Field(None, alias="orderRequestStatus")
    order_request_id: Optional[int] = Field(None, alias="orderRequestId")
    start_date: Optional[str] = Field(None, alias="startDate")  # 기존 호환성
    due_date: Optional[str] = Field(None, alias="dueDate")    # 기존 호환성
    start_datetime: Optional[datetime] = Field(None, alias="startDatetime")  # 새로운 DateTime 필드
    due_datetime: Optional[datetime] = Field(None, alias="dueDatetime")    # 새로운 DateTime 필드
    product_id: Optional[int] = Field(None, alias="productId")
    quantity: Optional[int] = 1
    cost: Optional[float] = None  # 포스트별 작업 단가
    product_cost: Optional[float] = Field(None, alias="productCost")  # 제품 단가 (원가)
    product_name: Optional[str] = Field(None, alias="productName")  # 제품명
    budget: Optional[float] = 0.0  # 포스트별 매출 예산
    assigned_user_id: Optional[int] = Field(None, alias="assignedUserId")  # 포스트 담당자


class PostUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    title: Optional[str] = None
    work_type: Optional[str] = Field(None, alias="workType")
    topic_status: Optional[str] = Field(None, alias="topicStatus")
    outline: Optional[str] = None
    outline_status: Optional[str] = Field(None, alias="outlineStatus")
    images: Optional[List[str]] = None
    published_url: Optional[str] = Field(None, alias="publishedUrl")
    order_request_status: Optional[str] = Field(None, alias="orderRequestStatus")
    order_request_id: Optional[int] = Field(None, alias="orderRequestId")
    start_date: Optional[str] = Field(None, alias="startDate")  # 기존 호환성
    due_date: Optional[str] = Field(None, alias="dueDate")    # 기존 호환성
    start_datetime: Optional[datetime] = Field(None, alias="startDatetime")  # 새로운 DateTime 필드
    due_datetime: Optional[datetime] = Field(None, alias="dueDatetime")    # 새로운 DateTime 필드
    product_id: Optional[int] = Field(None, alias="productId")
    quantity: Optional[int] = None
    cost: Optional[float] = None  # 포스트별 작업 단가
    product_cost: Optional[float] = Field(None, alias="productCost")  # 제품 단가 (원가)
    product_name: Optional[str] = Field(None, alias="productName")  # 제품명
    budget: Optional[float] = None  # 포스트별 매출 예산
    assigned_user_id: Optional[int] = Field(None, alias="assignedUserId")  # 포스트 담당자


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    title: str
    work_type: str = Field(alias="workType")
    topic_status: str = Field(alias="topicStatus")
    outline: Optional[str] = None
    outline_status: Optional[str] = Field(None, alias="outlineStatus")
    reject_reason: Optional[str] = Field(None, alias="rejectReason")  # 반려 사유
    images: Optional[List[str]] = None
    published_url: Optional[str] = Field(None, alias="publishedUrl")
    order_request_status: Optional[str] = Field(None, alias="orderRequestStatus")
    order_request_id: Optional[int] = Field(None, alias="orderRequestId")
    start_date: Optional[str] = Field(None, alias="startDate")  # 기존 호환성
    due_date: Optional[str] = Field(None, alias="dueDate")    # 기존 호환성
    start_datetime: Optional[datetime] = Field(None, alias="startDatetime")  # 새로운 DateTime 필드
    due_datetime: Optional[datetime] = Field(None, alias="dueDatetime")    # 새로운 DateTime 필드
    product_id: Optional[int] = Field(None, alias="productId")
    quantity: Optional[int] = None
    cost: Optional[float] = None  # 포스트별 작업 단가
    product_cost: Optional[float] = Field(None, alias="productCost")  # 제품 단가 (원가)
    product_name: Optional[str] = Field(None, alias="productName")  # 제품명
    budget: Optional[float] = 0.0  # 포스트별 매출 예산
    assigned_user_id: Optional[int] = Field(None, alias="assignedUserId")  # 포스트 담당자
    campaign_id: int = Field(alias="campaignId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
