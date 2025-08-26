from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

from app.models.user import UserRole, UserStatus


class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    role: UserRole
    company: Optional[str] = Field(None, max_length=200)
    contact: Optional[str] = Field(None, max_length=50)
    incentive_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=50)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    company: Optional[str] = Field(None, max_length=200)
    contact: Optional[str] = Field(None, max_length=50)
    incentive_rate: Optional[float] = Field(None, ge=0.0, le=100.0)
    status: Optional[UserStatus] = None
    password: Optional[str] = Field(None, min_length=6, max_length=50)


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

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse