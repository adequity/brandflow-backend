from sqlalchemy import Column, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class WorkType(Base, TimestampMixin):
    __tablename__ = "work_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<WorkType(id={self.id}, name={self.name})>"