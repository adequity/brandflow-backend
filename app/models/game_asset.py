"""
게임 에셋 모델
관리자가 등록한 게임용 이미지 에셋
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
import enum

from app.models.base import Base


class GameAssetType(str, enum.Enum):
    """게임 에셋 타입"""
    SPOT_DIFFERENCE = "틀린그림찾기"
    MEMORY = "기억력게임"
    MATCH = "같은그림찾기"


class GameAssetCategory(str, enum.Enum):
    """게임 에셋 카테고리"""
    FOOD = "음식"
    DRINK = "음료"
    DESSERT = "디저트"
    ETC = "기타"


class GameAsset(Base):
    """게임 에셋 테이블"""
    __tablename__ = "game_assets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="에셋 이름")
    category = Column(String(50), default="기타", comment="카테고리")
    game_type = Column(String(50), nullable=False, comment="사용 게임")
    image_url = Column(String(500), nullable=True, comment="이미지 URL")
    usage_count = Column(Integer, default=0, comment="사용 횟수")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
