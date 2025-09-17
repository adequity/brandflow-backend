from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from .base import Base, TimestampMixin


class SettingCategory(str, enum.Enum):
    BRANDING = "branding"
    WORKTYPE = "worktype"
    INCENTIVE = "incentive"
    SALES = "sales"
    DOCUMENT = "document"
    GENERAL = "general"
    DATABASE = "database"


class SettingType(str, enum.Enum):
    BOOLEAN = "boolean"
    STRING = "string"
    NUMBER = "number"
    JSON = "json"


class AccessLevel(str, enum.Enum):
    SUPER_ADMIN = "super_admin"  # 슈퍼 어드민만
    ADMIN = "admin"              # 모든 어드민
    USER = "user"                # 모든 사용자


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # 값 관련
    current_value = Column(Text, nullable=True)  # JSON string or plain text
    default_value = Column(Text, nullable=True)
    setting_type = Column(SQLEnum(SettingType), nullable=False, default=SettingType.STRING)

    # 분류 및 권한
    category = Column(SQLEnum(SettingCategory), nullable=False)
    access_level = Column(SQLEnum(AccessLevel), nullable=False, default=AccessLevel.ADMIN)

    # 상태
    is_active = Column(Boolean, default=True, nullable=False)
    is_system_default = Column(Boolean, default=False, nullable=False)  # 시스템 기본 설정인지

    # 수정자 정보
    modified_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # 관계
    modifier = relationship("User", foreign_keys=[modified_by])

    def __repr__(self):
        return f"<SystemSetting(key={self.setting_key}, value={self.current_value})>"

    @property
    def parsed_value(self):
        """타입에 따른 값 파싱"""
        if not self.current_value:
            return self.parsed_default_value

        try:
            if self.setting_type == SettingType.BOOLEAN:
                return self.current_value.lower() in ('true', '1', 'yes', 'on')
            elif self.setting_type == SettingType.NUMBER:
                return float(self.current_value) if '.' in self.current_value else int(self.current_value)
            elif self.setting_type == SettingType.JSON:
                import json
                return json.loads(self.current_value)
            else:
                return self.current_value
        except (ValueError, TypeError, json.JSONDecodeError):
            return self.parsed_default_value

    @property
    def parsed_default_value(self):
        """기본값 파싱"""
        if not self.default_value:
            return None

        try:
            if self.setting_type == SettingType.BOOLEAN:
                return self.default_value.lower() in ('true', '1', 'yes', 'on')
            elif self.setting_type == SettingType.NUMBER:
                return float(self.default_value) if '.' in self.default_value else int(self.default_value)
            elif self.setting_type == SettingType.JSON:
                import json
                return json.loads(self.default_value)
            else:
                return self.default_value
        except (ValueError, TypeError, json.JSONDecodeError):
            return None