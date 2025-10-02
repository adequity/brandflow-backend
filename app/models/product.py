from sqlalchemy import Column, Integer, String, Text, Float, Boolean

from .base import Base, TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    cost = Column(Float, nullable=False)
    category = Column(String(100), nullable=True)
    sku = Column(String(50), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    company = Column(String(200), nullable=True, index=True, default='default_company')  # 회사별 데이터 분리
    
    def __repr__(self):
        return f"<Product(id={self.id}, name={self.name}, price={self.price})>"