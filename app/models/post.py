from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .base import Base, TimestampMixin


class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    work_type = Column(String(100), nullable=False, default="블로그")
    topic_status = Column(String(50), nullable=False, default="주제 승인 대기")
    company = Column(String(200), nullable=True, index=True, default='default_company')  # 회사별 포스트 분리
    outline = Column(Text, nullable=True)
    outline_status = Column(String(50), nullable=True)
    reject_reason = Column(Text, nullable=True)  # 반려 사유
    images = Column(JSON, nullable=True, default=list)
    published_url = Column(Text, nullable=True)
    order_request_status = Column(String(50), nullable=True)
    order_request_id = Column(Integer, nullable=True)
    start_date = Column(String(20), nullable=True)  # 날짜를 문자열로 저장 (YYYY-MM-DD 형식) - 기존 호환성
    due_date = Column(String(20), nullable=True)    # 날짜를 문자열로 저장 (YYYY-MM-DD 형식) - 기존 호환성
    start_datetime = Column(DateTime, nullable=True)  # 시작 날짜/시간 (DateTime 타입)
    due_datetime = Column(DateTime, nullable=True)    # 마감 날짜/시간 (DateTime 타입)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    quantity = Column(Integer, nullable=True, default=1)
    cost = Column(Float, nullable=True)  # 포스트별 작업 단가
    product_cost = Column(Float, nullable=True)  # 제품 단가 (원가)
    product_name = Column(String(200), nullable=True)  # 제품명
    budget = Column(Float, nullable=True, default=0.0)  # 포스트별 매출 예산

    # 재무 관련 필드
    invoice_issued = Column(Boolean, default=False, nullable=True)  # 포스트별 계산서 발행 완료
    payment_completed = Column(Boolean, default=False, nullable=True)  # 포스트별 입금 완료
    invoice_due_date = Column(DateTime, nullable=True)  # 포스트별 계산서 발행 마감일
    payment_due_date = Column(DateTime, nullable=True)  # 포스트별 결제 마감일

    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 포스트 담당자
    is_active = Column(Boolean, default=True)

    # 관계 설정
    campaign = relationship("Campaign", back_populates="posts")
    product = relationship("Product")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])

    def __repr__(self):
        return f"<Post(id={self.id}, title={self.title}, campaign_id={self.campaign_id})>"