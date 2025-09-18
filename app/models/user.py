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
    company = Column(String(200), nullable=True)  # 관리용 대행사 소속
    business_number = Column(String(20), nullable=True)  # 사업자번호 추가
    contact = Column(String(50), nullable=True)

    # 클라이언트 실제 회사 정보 (계산서/견적서용)
    client_company_name = Column(String(200), nullable=True)  # 실제 회사명
    client_business_number = Column(String(20), nullable=True)  # 실제 사업자번호
    client_ceo_name = Column(String(100), nullable=True)  # 실제 대표자명
    client_company_address = Column(String(500), nullable=True)  # 실제 회사 주소
    client_business_type = Column(String(100), nullable=True)  # 실제 업태
    client_business_item = Column(String(100), nullable=True)  # 실제 종목
    incentive_rate = Column(Float, default=0.0)
    status = Column(SQLEnum(UserStatus), default=UserStatus.INACTIVE)
    is_active = Column(Boolean, default=True)

    # 관계 설정
    campaigns = relationship("Campaign", back_populates="creator", foreign_keys="Campaign.creator_id")
    purchase_requests = relationship("PurchaseRequest", back_populates="requester")
    sales_records = relationship("Sales", back_populates="employee")
    telegram_setting = relationship("UserTelegramSetting", back_populates="user", uselist=False)
    
    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, role={self.role})>"