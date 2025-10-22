from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Union
from datetime import datetime

from app.models.user import UserRole, UserStatus


class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    role: Union[UserRole, str]
    company: Optional[str] = Field(None, max_length=200)
    contact: Optional[str] = Field(None, max_length=50)
    incentive_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    # 사업자번호 (client_business_number와 동일하게 처리)
    business_number: Optional[str] = Field(None, max_length=20)

    # 클라이언트 실제 회사 정보 필드들
    client_company_name: Optional[str] = Field(None, max_length=200)
    client_business_number: Optional[str] = Field(None, max_length=20)
    client_ceo_name: Optional[str] = Field(None, max_length=100)
    client_company_address: Optional[str] = Field(None, max_length=500)
    client_business_type: Optional[str] = Field(None, max_length=100)
    client_business_item: Optional[str] = Field(None, max_length=100)

    # 팀 관련 필드 (TEAM_LEADER 시스템)
    team_name: Optional[str] = Field(None, max_length=100)
    team_leader_id: Optional[int] = None

    @validator('role', pre=True)
    def validate_role(cls, v):
        if isinstance(v, str):
            # 한글/영어 역할명을 영문 UserRole enum으로 변환
            role_mapping = {
                # 영문 → 영문 (정규화)
                'super_admin': 'SUPER_ADMIN',
                'agency_admin': 'AGENCY_ADMIN',
                'staff': 'STAFF',
                'client': 'CLIENT',
                # 대소문자 무관
                'SUPER_ADMIN': 'SUPER_ADMIN',
                'AGENCY_ADMIN': 'AGENCY_ADMIN',
                'STAFF': 'STAFF',
                'CLIENT': 'CLIENT',
                # 한글 → 영문 변환
                '슈퍼 어드민': 'SUPER_ADMIN',
                '슈퍼어드민': 'SUPER_ADMIN',
                '대행사 어드민': 'AGENCY_ADMIN',
                '대행사어드민': 'AGENCY_ADMIN',
                '직원': 'STAFF',
                '클라이언트': 'CLIENT'
            }
            # 매핑된 값으로 변환
            mapped_value = role_mapping.get(v, role_mapping.get(v.lower(), v))
            # UserRole enum으로 반환
            try:
                return UserRole(mapped_value)
            except ValueError:
                # 변환할 수 없는 경우 기본값 반환
                return UserRole.CLIENT
        return v


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=50)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[Union[UserRole, str]] = None
    company: Optional[str] = Field(None, max_length=200)
    contact: Optional[str] = Field(None, max_length=50)
    incentive_rate: Optional[float] = Field(None, ge=0.0, le=100.0)
    status: Optional[UserStatus] = None
    password: Optional[str] = Field(None, min_length=6, max_length=50)

    # 사업자번호 (client_business_number와 동일하게 처리)
    business_number: Optional[str] = Field(None, max_length=20)

    # 클라이언트 실제 회사 정보 필드들
    client_company_name: Optional[str] = Field(None, max_length=200)
    client_business_number: Optional[str] = Field(None, max_length=20)
    client_ceo_name: Optional[str] = Field(None, max_length=100)
    client_company_address: Optional[str] = Field(None, max_length=500)
    client_business_type: Optional[str] = Field(None, max_length=100)
    client_business_item: Optional[str] = Field(None, max_length=100)

    # 팀 관련 필드 (TEAM_LEADER 시스템)
    team_name: Optional[str] = Field(None, max_length=100)
    team_leader_id: Optional[int] = None

    @validator('role', pre=True)
    def validate_role(cls, v):
        if isinstance(v, str):
            # 한글/영어 역할명을 영문 UserRole enum으로 변환
            role_mapping = {
                # 영문 → 영문 (정규화)
                'super_admin': 'SUPER_ADMIN',
                'agency_admin': 'AGENCY_ADMIN',
                'staff': 'STAFF',
                'client': 'CLIENT',
                # 대소문자 무관
                'SUPER_ADMIN': 'SUPER_ADMIN',
                'AGENCY_ADMIN': 'AGENCY_ADMIN',
                'STAFF': 'STAFF',
                'CLIENT': 'CLIENT',
                # 한글 → 영문 변환
                '슈퍼 어드민': 'SUPER_ADMIN',
                '슈퍼어드민': 'SUPER_ADMIN',
                '대행사 어드민': 'AGENCY_ADMIN',
                '대행사어드민': 'AGENCY_ADMIN',
                '직원': 'STAFF',
                '클라이언트': 'CLIENT'
            }
            # 매핑된 값으로 변환
            mapped_value = role_mapping.get(v, role_mapping.get(v.lower(), v))
            # UserRole enum으로 반환
            try:
                return UserRole(mapped_value)
            except ValueError:
                # 변환할 수 없는 경우 기본값 반환
                return UserRole.CLIENT
        return v


class UserResponse(BaseModel):
    id: int
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    role: UserRole
    company: Optional[str] = Field(None, max_length=200)
    contact: Optional[str] = Field(None, max_length=50)
    incentive_rate: Optional[float] = Field(default=0.0, ge=0.0, le=100.0)
    status: UserStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # 사업자번호 (client_business_number와 동일하게 처리)
    business_number: Optional[str] = Field(None, max_length=20)

    # 클라이언트 실제 회사 정보 필드들
    client_company_name: Optional[str] = Field(None, max_length=200)
    client_business_number: Optional[str] = Field(None, max_length=20)
    client_ceo_name: Optional[str] = Field(None, max_length=100)
    client_company_address: Optional[str] = Field(None, max_length=500)
    client_business_type: Optional[str] = Field(None, max_length=100)
    client_business_item: Optional[str] = Field(None, max_length=100)

    # 팀 관련 필드 (TEAM_LEADER 시스템)
    team_name: Optional[str] = None
    team_leader_id: Optional[int] = None

    @validator('business_number', pre=False, always=True)
    def sync_business_number(cls, v, values):
        """business_number를 client_business_number와 동기화"""
        return values.get('client_business_number') or v

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse