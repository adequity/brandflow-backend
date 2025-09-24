from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .base import Base, TimestampMixin


class UserTelegramSetting(Base, TimestampMixin):
    """사용자별 텔레그램 알림 설정"""
    __tablename__ = "user_telegram_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    telegram_chat_id = Column(String(100), nullable=False, index=True)
    telegram_username = Column(String(100), nullable=True)  # 사용자 확인용

    # 알림 설정
    is_enabled = Column(Boolean, default=True, nullable=False)
    days_before_due = Column(Integer, default=2, nullable=False)  # 마감일 며칠 전 알림
    notification_time = Column(String(5), default="09:00", nullable=False)  # 알림 시간 (HH:MM)

    # 마지막 알림 기록
    last_notification_at = Column(DateTime, nullable=True)

    # 관계
    user = relationship("User", back_populates="telegram_setting")

    def __repr__(self):
        return f"<UserTelegramSetting(user_id={self.user_id}, chat_id={self.telegram_chat_id})>"


class TelegramNotificationLog(Base, TimestampMixin):
    """텔레그램 알림 발송 로그"""
    __tablename__ = "telegram_notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)  # 테스트 메시지는 None 가능
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)  # 테스트 메시지는 None 가능

    # 알림 정보
    notification_type = Column(String(50), default="due_date_reminder", nullable=False)
    message_content = Column(String(1000), nullable=False)
    telegram_chat_id = Column(String(100), nullable=False)

    # 발송 결과
    is_sent = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(String(500), nullable=True)
    telegram_message_id = Column(String(100), nullable=True)  # 텔레그램 메시지 ID

    # 관계
    user = relationship("User")
    post = relationship("Post")
    campaign = relationship("Campaign")

    def __repr__(self):
        return f"<TelegramNotificationLog(user_id={self.user_id}, post_id={self.post_id}, sent={self.is_sent})>"