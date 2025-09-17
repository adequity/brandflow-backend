from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class TelegramSettingBase(BaseModel):
    telegram_chat_id: str = Field(..., min_length=1, max_length=100, description="텔레그램 채팅 ID")
    telegram_username: Optional[str] = Field(None, max_length=100, description="텔레그램 사용자명")
    is_enabled: bool = Field(True, description="알림 활성화 여부")
    days_before_due: int = Field(2, ge=1, le=30, description="마감일 며칠 전 알림")
    notification_time: str = Field("09:00", description="알림 시간 (HH:MM)")

    @validator('notification_time')
    def validate_time_format(cls, v):
        import re
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError('시간 형식은 HH:MM이어야 합니다 (예: 09:00)')
        return v

    @validator('telegram_chat_id')
    def validate_chat_id(cls, v):
        # 텔레그램 채팅 ID는 숫자 또는 @로 시작하는 문자열
        if not (v.isdigit() or (v.startswith('@') and len(v) > 1)):
            raise ValueError('올바른 텔레그램 채팅 ID 형식이 아닙니다')
        return v


class TelegramSettingCreate(TelegramSettingBase):
    pass


class TelegramSettingUpdate(BaseModel):
    telegram_chat_id: Optional[str] = Field(None, min_length=1, max_length=100)
    telegram_username: Optional[str] = Field(None, max_length=100)
    is_enabled: Optional[bool] = None
    days_before_due: Optional[int] = Field(None, ge=1, le=30)
    notification_time: Optional[str] = None

    @validator('notification_time')
    def validate_time_format(cls, v):
        if v is not None:
            import re
            if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', v):
                raise ValueError('시간 형식은 HH:MM이어야 합니다 (예: 09:00)')
        return v

    @validator('telegram_chat_id')
    def validate_chat_id(cls, v):
        if v is not None:
            if not (v.isdigit() or (v.startswith('@') and len(v) > 1)):
                raise ValueError('올바른 텔레그램 채팅 ID 형식이 아닙니다')
        return v


class TelegramSettingResponse(TelegramSettingBase):
    id: int
    user_id: int
    last_notification_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TelegramTestRequest(BaseModel):
    message: str = Field("테스트 메시지입니다.", description="전송할 테스트 메시지")


class TelegramNotificationLogResponse(BaseModel):
    id: int
    user_id: int
    post_id: int
    campaign_id: int
    notification_type: str
    message_content: str
    is_sent: bool
    sent_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TelegramStatsResponse(BaseModel):
    total_users_with_telegram: int
    active_notifications: int
    notifications_sent_today: int
    notifications_failed_today: int
    upcoming_deadlines: int