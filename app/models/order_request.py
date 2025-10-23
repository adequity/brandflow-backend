from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base, TimestampMixin


class OrderRequest(Base, TimestampMixin):
    __tablename__ = "order_requests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="대기")  # 대기, 승인, 거부, 완료

    # 요청자 소속 정보 (발주 생성 시 user 정보에서 자동 복사)
    company = Column(String(200), nullable=True, index=True, default='default_company')  # 요청자 회사
    requester_role = Column(String(50), nullable=True, index=True)  # 요청자 역할 (STAFF, TEAM_LEADER 등)
    team_leader_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # 요청자의 팀장 ID (STAFF인 경우)

    cost_price = Column(Integer, nullable=True)  # 원가 (원 단위)
    resource_type = Column(String(100), nullable=True)

    # 관계 필드
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # 발주 요청자
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)

    # 상태 필드
    is_active = Column(Boolean, default=True)

    # 관계 설정
    post = relationship("Post")
    user = relationship("User")
    campaign = relationship("Campaign")

    def __repr__(self):
        return f"<OrderRequest(id={self.id}, title={self.title}, status={self.status})>"