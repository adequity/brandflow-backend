from sqlalchemy import Column, Integer, String, Float, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
import enum

from .base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "슈퍼 어드민"
    AGENCY_ADMIN = "대행사 어드민"
    STAFF = "직원"
    CLIENT = "클라이언트"


class UserStatus(str, enum.Enum):
    ACTIVE = "활성"
    INACTIVE = "휴면"
    BANNED = "차단"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    company = Column(String(200), nullable=True)
    contact = Column(String(50), nullable=True)
    incentive_rate = Column(Float, default=0.0)
    status = Column(SQLEnum(UserStatus), default=UserStatus.INACTIVE)
    is_active = Column(Boolean, default=True)

    # 관계 설정
    campaigns = relationship("Campaign", foreign_keys="Campaign.creator_id", back_populates="creator")
    purchase_requests = relationship("PurchaseRequest", back_populates="requester")
    sales_records = relationship("Sales", back_populates="employee")
    
    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, role={self.role})>"