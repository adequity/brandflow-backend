from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)  # This will be the cost price from frontend
    cost = Column(Float, nullable=False)   # Keeping for backward compatibility
    selling_price = Column(Float, nullable=True)  # Optional recommended selling price
    category = Column(String(100), nullable=True)  # Keeping for backward compatibility
    work_type_id = Column(Integer, ForeignKey("work_types.id"), nullable=True)  # New work_type relation
    sku = Column(String(50), unique=True, nullable=True)
    unit = Column(String(20), default="건")
    min_quantity = Column(Integer, default=1)
    max_quantity = Column(Integer, nullable=True)
    tags = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)

    # 관계 설정
    work_type = relationship("WorkType")  # work_type과의 관계
    
    def __repr__(self):
        return f"<Product(id={self.id}, name={self.name}, price={self.price})>"