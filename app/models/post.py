from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .base import Base, TimestampMixin


class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    work_type = Column(String(100), nullable=False, default="블로그")
    topic_status = Column(String(50), nullable=False, default="대기")
    outline = Column(Text, nullable=True)
    outline_status = Column(String(50), nullable=True)
    images = Column(JSON, nullable=True, default=list)
    published_url = Column(Text, nullable=True)
    order_request_status = Column(String(50), nullable=True)
    order_request_id = Column(Integer, nullable=True)
    start_date = Column(String(20), nullable=True)  # 날짜를 문자열로 저장 (YYYY-MM-DD 형식) - 기존 호환성
    due_date = Column(String(20), nullable=True)    # 날짜를 문자열로 저장 (YYYY-MM-DD 형식) - 기존 호환성
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    quantity = Column(Integer, nullable=True, default=1)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    is_active = Column(Boolean, default=True)

    # 관계 설정
    campaign = relationship("Campaign", back_populates="posts")
    product = relationship("Product")

    def __repr__(self):
        return f"<Post(id={self.id}, title={self.title}, campaign_id={self.campaign_id})>"