from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from urllib.parse import unquote

from app.db.database import get_async_db
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.services.user_service import UserService
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.core.security import get_password_hash

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def get_users(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    # 기존 파라미터도 지원
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    role: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """사용자 목록 조회 (권한별 필터링)"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 현재 사용자 조회
        current_user_query = select(User).where(User.id == user_id)
        result = await db.execute(current_user_query)
        current_user = result.scalar_one_or_none()
        
        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 권한별 필터링 (UserRole enum 값 사용)
        if user_role == UserRole.SUPER_ADMIN.value or 'super' in user_role.lower():
            # 슈퍼 어드민은 모든 사용자 조회 가능
            query = select(User)
        elif user_role == UserRole.AGENCY_ADMIN.value or ('agency' in user_role.lower() and 'admin' in user_role.lower()):
            # 대행사 어드민은 같은 회사 사용자만 조회 가능
            query = select(User).where(User.company == current_user.company)
        elif user_role == UserRole.CLIENT.value:
            # 클라이언트는 자신만 조회 가능
            query = select(User).where(User.id == user_id)
        elif user_role == UserRole.STAFF.value:
            # 직원은 같은 회사 사용자만 조회 가능
            query = select(User).where(User.company == current_user.company)
        else:
            # 기본값: 같은 회사 사용자만 조회 가능
            query = select(User).where(User.company == current_user.company)
        
        result = await db.execute(query)
        users = result.scalars().all()
        
        return users
    else:
        # JWT 기반 권한별 필터링
        user_role = jwt_user.role
        
        # JWT 기반 권한별 필터링 (UserRole enum 값 사용)
        if user_role == UserRole.SUPER_ADMIN:
            # 슈퍼 어드민은 모든 사용자 조회 가능
            query = select(User)
        elif user_role == UserRole.AGENCY_ADMIN:
            # 대행사 어드민은 같은 회사 사용자만 조회 가능
            query = select(User).where(User.company == jwt_user.company)
        elif user_role == UserRole.CLIENT:
            # 클라이언트는 자신만 조회 가능
            query = select(User).where(User.id == jwt_user.id)
        elif user_role == UserRole.STAFF:
            # 직원은 같은 회사 사용자만 조회 가능
            query = select(User).where(User.company == jwt_user.company)
        else:
            # 기본값: 같은 회사 사용자만 조회 가능
            query = select(User).where(User.company == jwt_user.company)
        
        # 페이지네이션 적용
        query = query.offset(skip).limit(limit)
        
        # 추가 필터링
        if role:
            query = query.where(User.role == role)
        if company:
            query = query.where(User.company == company)
        
        result = await db.execute(query)
        users = result.scalars().all()
        
        return users


@router.get("/clients", response_model=List[UserResponse])
async def get_clients(
    # Node.js API 호환성을 위한 쿼리 파라미터 (보안상 제거 예정)
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    # JWT 인증된 사용자
    jwt_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """클라이언트 목록 조회 (권한별 필터링)"""
    # 기존 API 호환 모드 vs JWT 모드 구분
    if viewerId is not None or adminId is not None:
        # 기존 API 호환 모드 (보안상 제거 예정)
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 현재 사용자 조회
        current_user_query = select(User).where(User.id == user_id)
        result = await db.execute(current_user_query)
        current_user = result.scalar_one_or_none()
        
        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 클라이언트만 필터링
        query = select(User).where(User.role == UserRole.CLIENT)
        
        # 권한별 추가 필터링 (UserRole enum 값 사용)
        if user_role == UserRole.AGENCY_ADMIN.value or ('agency' in user_role.lower() and 'admin' in user_role.lower()):
            # 대행사 어드민은 같은 회사 클라이언트만 조회 가능
            query = query.where(User.company == current_user.company)
        elif user_role == UserRole.CLIENT.value:
            # 클라이언트는 자신만 조회 가능
            query = query.where(User.id == user_id)
        elif user_role == UserRole.STAFF.value:
            # 직원은 같은 회사 클라이언트 조회 가능
            query = query.where(User.company == current_user.company)
        # 슈퍼 어드민은 모든 클라이언트 조회 가능 (추가 필터링 없음)
        
        result = await db.execute(query)
        clients = result.scalars().all()
        
        return clients
    else:
        # JWT 인증 기반 모드 (보안 강화)
        current_user = jwt_user
        user_id = current_user.id
        user_role = current_user.role.value
        
        print(f"[USERS-CLIENTS-JWT] User: {current_user.name}, Role: {user_role}, Company: {current_user.company}")
        
        # 클라이언트만 필터링
        query = select(User).where(User.role == UserRole.CLIENT)
        
        # JWT 기반 권한별 필터링 (UserRole enum 값 사용)
        if user_role == UserRole.SUPER_ADMIN.value:
            # 슈퍼 어드민은 모든 클라이언트 조회 가능
            pass
        elif user_role == UserRole.AGENCY_ADMIN.value:
            # 대행사 어드민은 같은 회사 클라이언트만 조회 가능
            query = query.where(User.company == current_user.company)
        elif user_role == UserRole.CLIENT.value:
            # 클라이언트는 자신만 조회 가능
            query = query.where(User.id == user_id)
        elif user_role == UserRole.STAFF.value:
            # 직원은 같은 회사 클라이언트 조회 가능
            query = query.where(User.company == current_user.company)
        else:
            # 기타 역할은 클라이언트 조회 불가
            return []
        
        result = await db.execute(query)
        clients = result.scalars().all()
        
        print(f"[USERS-CLIENTS-JWT] Found {len(clients)} clients")
        return clients


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """현재 사용자 정보 조회"""
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """특정 사용자 정보 조회"""
    service = UserService(db)
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    
    # 권한 확인
    if not service.can_view_user(current_user, user):
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    
    return user


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """새 사용자 생성 (권한 확인)"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 권한 확인 - 관리자와 직원은 사용자 생성 가능 (한글/영어 역할명 모두 지원)
        is_admin = (user_role in ['슈퍼 어드민', '슈퍼어드민', '대행사 어드민', '대행사어드민', 'super_admin', 'agency_admin'] or 
                    '슈퍼' in user_role or 'super' in user_role.lower() or 
                    ('대행사' in user_role and '어드민' in user_role) or 
                    ('agency' in user_role.lower() and 'admin' in user_role.lower()))
        is_staff = (user_role in ['직원', 'staff'])
        
        if not (is_admin or is_staff):
            raise HTTPException(status_code=403, detail="권한이 없습니다. 관리자와 직원만 사용자를 생성할 수 있습니다.")
        
        # 직원의 경우 클라이언트 계정만 생성 가능
        if is_staff and not is_admin:
            if user_data.role not in ['클라이언트', 'client']:
                raise HTTPException(status_code=403, detail="직원은 클라이언트 계정만 생성할 수 있습니다.")
        
        # 현재 사용자 정보 조회 (회사 확인을 위해)
        current_user_query = select(User).where(User.id == user_id)
        current_user_result = await db.execute(current_user_query)
        current_user = current_user_result.scalar_one_or_none()
        
        if not current_user:
            raise HTTPException(status_code=404, detail="현재 사용자를 찾을 수 없습니다.")
        
        # 직원의 경우 같은 회사의 클라이언트만 생성 가능
        if is_staff and not is_admin:
            user_data.company = current_user.company
        
        # 이메일 중복 확인
        existing_user_query = select(User).where(User.email == user_data.email)
        result = await db.execute(existing_user_query)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다")
        
        # 새 사용자 생성 (Pydantic validator에서 이미 역할명 변환됨)
        hashed_password = get_password_hash(user_data.password)

        new_user = User(
            name=user_data.name,
            email=user_data.email,
            hashed_password=hashed_password,
            role=user_data.role,
            company=user_data.company,
            contact=user_data.contact,
            incentive_rate=user_data.incentive_rate or 0.0,
            is_active=True,
            # 클라이언트 실제 회사 정보 필드들
            client_company_name=user_data.client_company_name,
            client_business_number=user_data.client_business_number,
            client_ceo_name=user_data.client_ceo_name,
            client_company_address=user_data.client_company_address,
            client_business_type=user_data.client_business_type,
            client_business_item=user_data.client_business_item
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        return new_user
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        service = UserService(db)
        
        # 권한 확인
        if not service.can_create_user(current_user, user_data.role):
            raise HTTPException(status_code=403, detail="사용자 생성 권한이 없습니다.")
        
        # 이메일 중복 확인
        existing_user = await service.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")
        
        return await service.create_user(user_data)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """사용자 정보 수정"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        viewer_id = viewerId or adminId
        viewer_role = viewerRole or adminRole
        
        if not viewer_id or not viewer_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        viewer_role = unquote(viewer_role).strip()
        
        # 수정할 사용자 조회
        user_query = select(User).where(User.id == user_id)
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 권한 확인 (한글/영어 역할명 모두 지원)
        is_super_admin = (viewer_role in ['슈퍼 어드민', '슈퍼어드민', 'super_admin'] or 
                         '슈퍼' in viewer_role or 'super' in viewer_role.lower())
        is_agency_admin = (viewer_role in ['대행사 어드민', '대행사어드민', 'agency_admin'] or 
                          ('대행사' in viewer_role and '어드민' in viewer_role) or 
                          ('agency' in viewer_role.lower() and 'admin' in viewer_role.lower()))
        
        if not is_super_admin and not is_agency_admin:
            raise HTTPException(status_code=403, detail="권한이 없습니다. 관리자만 사용자 정보를 수정할 수 있습니다.")
        
        # 대행사 어드민의 경우 같은 회사 사용자만 수정 가능
        if is_agency_admin and not is_super_admin:
            viewer_query = select(User).where(User.id == viewer_id)
            viewer_result = await db.execute(viewer_query)
            viewer = viewer_result.scalar_one_or_none()
            
            if not viewer or user.company != viewer.company:
                raise HTTPException(status_code=403, detail="같은 회사 소속 사용자만 수정할 수 있습니다.")
        
        # 사용자 정보 업데이트
        update_data = user_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if field == 'password' and value:
                # 비밀번호는 해시화해서 저장
                setattr(user, 'hashed_password', get_password_hash(value))
            elif hasattr(user, field):
                setattr(user, field, value)
            elif field in ['client_company_name', 'client_business_number', 'client_ceo_name',
                          'client_company_address', 'client_business_type', 'client_business_item']:
                # 클라이언트 실제 회사 정보 필드들 처리
                setattr(user, field, value)
        
        await db.commit()
        await db.refresh(user)
        
        return user
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        service = UserService(db)
        
        # 사용자 존재 확인
        user = await service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        # 권한 확인
        if not service.can_update_user(current_user, user):
            raise HTTPException(status_code=403, detail="사용자 수정 권한이 없습니다.")
        
        # 이메일 중복 확인 (변경하는 경우)
        if user_data.email and user_data.email != user.email:
            existing_user = await service.get_user_by_email(user_data.email)
            if existing_user:
                raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")
        
        return await service.update_user(user_id, user_data)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """사용자 삭제"""
    service = UserService(db)
    
    # 사용자 존재 확인
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    
    # 권한 확인
    if not service.can_delete_user(current_user, user):
        raise HTTPException(status_code=403, detail="사용자 삭제 권한이 없습니다.")
    
    await service.delete_user(user_id)
    return {"message": "사용자가 삭제되었습니다."}