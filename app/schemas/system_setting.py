from pydantic import BaseModel, Field, validator
from typing import Optional, Any, Dict, List
from datetime import datetime
from app.models.system_setting import SettingCategory, SettingType, AccessLevel


class SystemSettingBase(BaseModel):
    setting_key: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    setting_type: SettingType
    category: SettingCategory
    access_level: AccessLevel = AccessLevel.ADMIN
    is_active: bool = True

    @validator('setting_key')
    def validate_setting_key(cls, v):
        # 키 형식 검증 (영문, 숫자, 밑줄, 점만 허용)
        import re
        if not re.match(r'^[a-zA-Z0-9._-]+$', v):
            raise ValueError('설정 키는 영문, 숫자, 밑줄, 점, 하이픈만 허용됩니다')
        return v


class SystemSettingCreate(SystemSettingBase):
    current_value: Optional[str] = None
    default_value: Optional[str] = None
    is_system_default: bool = False


class SystemSettingUpdate(BaseModel):
    current_value: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    access_level: Optional[AccessLevel] = None


class SystemSettingResponse(SystemSettingBase):
    id: int
    current_value: Optional[str]
    default_value: Optional[str]
    parsed_value: Any
    parsed_default_value: Any
    is_system_default: bool
    created_at: datetime
    updated_at: datetime
    modified_by: Optional[int]

    class Config:
        from_attributes = True


class SystemSettingBulkUpdate(BaseModel):
    settings: Dict[str, Any] = Field(..., description="설정 키와 값의 매핑")


class SystemSettingListResponse(BaseModel):
    total: int
    settings: List[SystemSettingResponse]
    categories: List[str] = Field(default_factory=lambda: [cat.value for cat in SettingCategory])
    access_levels: List[str] = Field(default_factory=lambda: [level.value for level in AccessLevel])


class SystemSettingStats(BaseModel):
    total_settings: int
    active_settings: int
    by_category: Dict[str, int]
    by_access_level: Dict[str, int]
    by_type: Dict[str, int]
    modified_today: int