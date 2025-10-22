from sqlalchemy import Column, Integer, String, Float, Enum as SQLEnum, Boolean, ForeignKey
from sqlalchemy.orm import relationship
import enum

from .base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    AGENCY_ADMIN = "AGENCY_ADMIN"
    TEAM_LEADER = "TEAM_LEADER"
    STAFF = "STAFF"
    CLIENT = "CLIENT"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BANNED = "BANNED"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    company = Column(String(200), nullable=True)  # 관리용 대행사 소속
    contact = Column(String(50), nullable=True)

    # 클라이언트 실제 회사 정보 (계산서/견적서용)
    client_company_name = Column(String(200), nullable=True)  # 실제 회사명
    client_business_number = Column(String(20), nullable=True)  # 실제 사업자번호 (business_number도 겸용)
    client_ceo_name = Column(String(100), nullable=True)  # 실제 대표자명
    client_company_address = Column(String(500), nullable=True)  # 실제 회사 주소
    client_business_type = Column(String(100), nullable=True)  # 실제 업태
    client_business_item = Column(String(100), nullable=True)  # 실제 종목
    incentive_rate = Column(Float, default=0.0)
    status = Column(SQLEnum(UserStatus), default=UserStatus.INACTIVE)
    is_active = Column(Boolean, default=True)

    # STAFF가 CLIENT를 생성한 경우, 해당 STAFF의 ID를 기록
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    # 팀 관련 필드 (TEAM_LEADER 시스템)
    # team_id 제거: team_leader_id가 이미 팀 식별자로 사용되므로 중복
    team_name = Column(String(100), nullable=True)  # 팀 이름
    team_leader_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # 소속 팀장 ID

    # 관계 설정
    campaigns = relationship("Campaign", back_populates="creator", foreign_keys="Campaign.creator_id")
    purchase_requests = relationship("PurchaseRequest", back_populates="requester")
    sales_records = relationship("Sales", back_populates="employee")
    telegram_setting = relationship("UserTelegramSetting", back_populates="user", uselist=False)
    monthly_incentives = relationship("MonthlyIncentive", foreign_keys="MonthlyIncentive.user_id", back_populates="user")

    # 팀 관계 설정
    team_leader = relationship("User", remote_side=[id], foreign_keys=[team_leader_id], backref="team_members")
    
    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, role={self.role})>"