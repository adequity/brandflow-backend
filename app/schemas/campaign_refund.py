from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CampaignCancelRequest(BaseModel):
    """캠페인 취소 요청"""
    cancellation_reason: Optional[str] = None
    refund_type: str = "전액환불"  # "전액환불" or "부분환불"
    refund_amount: Optional[float] = None  # 부분환불 시 필수
    cancel_posts: bool = True  # 모든 업무도 취소할지


class PostRefundRequest(BaseModel):
    """개별 업무 환불 요청"""
    refund_type: str = "전액환불"
    refund_amount: Optional[float] = None
    refund_reason: Optional[str] = None


class RefundResponse(BaseModel):
    """환불 기록 응답"""
    id: int
    campaign_id: int
    refund_type: str
    refund_amount: float
    original_amount: float
    refund_reason: Optional[str] = None
    status: str
    cancel_invoice_url: Optional[str] = None
    cancel_invoice_name: Optional[str] = None
    requested_by: int
    requester_name: Optional[str] = None
    approved_by: Optional[int] = None
    approver_name: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PostRefundResponse(BaseModel):
    """업무 환불 기록 응답"""
    id: int
    post_id: int
    campaign_id: int
    refund_type: str
    refund_amount: float
    original_budget: float
    refund_reason: Optional[str] = None
    status: str
    cancel_invoice_url: Optional[str] = None
    cancel_invoice_name: Optional[str] = None
    requested_by: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RefundSummaryResponse(BaseModel):
    """환불 요약 응답"""
    campaign_id: int
    campaign_name: str
    original_budget: float
    total_refunded: float
    remaining_amount: float
    is_fully_refunded: bool
    campaign_refunds: List[RefundResponse] = []
    post_refunds: List[PostRefundResponse] = []
