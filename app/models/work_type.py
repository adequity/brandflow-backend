from sqlalchemy import Column, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class WorkType(Base, TimestampMixin):
    __tablename__ = "work_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # unique 제약 제거 (회사별로 중복 가능)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True, default='#6B7280')  # RGB 색상 코드 (#RRGGBB)
    company = Column(String(200), nullable=True, index=True, default='default_company')  # 회사별 업무타입 분리
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<WorkType(id={self.id}, name={self.name})>"