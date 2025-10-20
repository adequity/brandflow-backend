from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import datetime

from app.models.user import User, UserRole, UserStatus
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_users(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        role: Optional[str] = None,
        company: Optional[str] = None,
        viewer: Optional[User] = None
    ) -> List[User]:
        """사용자 목록 조회"""
        query = select(User)
        
        # 필터링 조건 추가
        conditions = []
        if role:
            conditions.append(User.role == role)
        if company:
            conditions.append(User.company.ilike(f"%{company}%"))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # 권한에 따른 필터링
        if viewer and viewer.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
            # 일반 직원은 자신의 정보만 볼 수 있음
            query = query.where(User.id == viewer.id)
        
        query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """ID로 사용자 조회"""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_user(self, user_data: UserCreate, creator_id: Optional[int] = None) -> User:
        """새 사용자 생성"""
        hashed_password = get_password_hash(user_data.password)

        # business_number와 client_business_number 동기화
        business_num = user_data.business_number or user_data.client_business_number

        db_user = User(
            name=user_data.name,
            email=user_data.email,
            hashed_password=hashed_password,
            role=user_data.role,
            company=user_data.company,
            contact=user_data.contact,
            incentive_rate=user_data.incentive_rate,
            status=UserStatus.INACTIVE,  # 기본적으로 휴면 상태
            is_active=True,
            # 클라이언트 실제 회사 정보
            client_company_name=user_data.client_company_name,
            client_business_number=business_num,
            client_ceo_name=user_data.client_ceo_name,
            client_company_address=user_data.client_company_address,
            client_business_type=user_data.client_business_type,
            client_business_item=user_data.client_business_item,
            # STAFF가 CLIENT를 생성한 경우 created_by 기록
            created_by=creator_id if user_data.role == UserRole.CLIENT else None
        )
        
        self.db.add(db_user)
        await self.db.flush()
        await self.db.refresh(db_user)
        return db_user

    async def update_user(self, user_id: int, user_data: UserUpdate) -> Optional[User]:
        """사용자 정보 수정"""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        db_user = result.scalar_one_or_none()

        if not db_user:
            return None

        # 업데이트할 필드들
        update_data = user_data.dict(exclude_unset=True)

        # 비밀번호 처리
        if "password" in update_data:
            if update_data["password"]:  # 빈 문자열이 아닌 경우만
                update_data["hashed_password"] = get_password_hash(update_data["password"])
            del update_data["password"]

        # business_number와 client_business_number 동기화
        if "business_number" in update_data or "client_business_number" in update_data:
            business_num = update_data.get("business_number") or update_data.get("client_business_number")
            if business_num:
                update_data["client_business_number"] = business_num
            # business_number 필드는 실제 컬럼이 아니므로 제거
            if "business_number" in update_data:
                del update_data["business_number"]

        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        db_user.updated_at = datetime.utcnow()
        
        await self.db.flush()
        await self.db.refresh(db_user)
        return db_user

    async def delete_user(self, user_id: int) -> bool:
        """사용자 삭제"""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        db_user = result.scalar_one_or_none()
        
        if not db_user:
            return False
        
        await self.db.delete(db_user)
        return True

    def can_view_user(self, viewer: User, target: User) -> bool:
        """사용자 조회 권한 확인"""
        if viewer.role in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
            return True
        return viewer.id == target.id

    def can_create_user(self, creator: User, target_role: UserRole) -> bool:
        """사용자 생성 권한 확인"""
        if creator.role == UserRole.SUPER_ADMIN:
            return True
        
        if creator.role == UserRole.AGENCY_ADMIN:
            # 대행사 어드민은 슈퍼 어드민을 제외한 모든 역할 생성 가능
            return target_role != UserRole.SUPER_ADMIN
        
        return False

    def can_update_user(self, updater: User, target: User) -> bool:
        """사용자 수정 권한 확인"""
        if updater.role == UserRole.SUPER_ADMIN:
            return True
        
        if updater.role == UserRole.AGENCY_ADMIN:
            # 대행사 어드민은 슈퍼 어드민을 제외한 모든 사용자 수정 가능
            return target.role != UserRole.SUPER_ADMIN
        
        # 일반 사용자는 자신의 정보만 수정 가능
        return updater.id == target.id

    def can_delete_user(self, deleter: User, target: User) -> bool:
        """사용자 삭제 권한 확인"""
        if deleter.role == UserRole.SUPER_ADMIN:
            # 슈퍼 어드민은 자신을 제외한 모든 사용자 삭제 가능
            return deleter.id != target.id
        
        if deleter.role == UserRole.AGENCY_ADMIN:
            # 대행사 어드민은 슈퍼 어드민과 자신을 제외한 모든 사용자 삭제 가능
            return target.role != UserRole.SUPER_ADMIN and deleter.id != target.id
        
        return False