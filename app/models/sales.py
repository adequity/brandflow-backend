from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from .base import Base, TimestampMixin


class SalesStatus(str, enum.Enum):
    PENDING = "대기"
    CONFIRMED = "확정"
    CANCELLED = "취소"


class Sales(Base, TimestampMixin):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(200), nullable=False)
    product_name = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    commission = Column(Float, nullable=False)
    sale_date = Column(DateTime, nullable=False)
    status = Column(SQLEnum(SalesStatus), default=SalesStatus.PENDING)
    
    # 외래키
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    
    # 관계 설정
    employee = relationship("User", back_populates="sales_records")
    product = relationship("Product")
    
    def __repr__(self):
        return f"<Sales(id={self.id}, client={self.client_name}, amount={self.total_amount})>"