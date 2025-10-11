from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from urllib.parse import unquote
from pydantic import BaseModel

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.models.work_type import WorkType

router = APIRouter()


# Pydantic 스키마
class WorkTypeCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    sortOrder: Optional[int] = 0


class WorkTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sortOrder: Optional[int] = None


@router.get("/", response_model=List[dict])
async def get_work_types(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """작업 유형 목록 조회"""
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
        
        # 작업 유형 조회 (Node.js API 모드) - 회사별 필터링 (스키마 체크)
        user_company = current_user.company or 'default_company'

        # company 컬럼 존재 여부 확인
        from sqlalchemy import text
        check_column_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'work_types' AND column_name = 'company'
        """)
        column_result = await db.execute(check_column_query)
        company_column_exists = column_result.fetchone() is not None

        if company_column_exists:
            # company 컬럼이 있는 경우 회사별 필터링
            query = select(WorkType).where(
                WorkType.is_active == True,
                (WorkType.company == user_company) | (WorkType.company.is_(None))
            )
            print(f"[WORK-TYPES] Using company filtering for user company: {user_company}")
        else:
            # company 컬럼이 없는 경우 fallback
            query = select(WorkType).where(WorkType.is_active == True)
            print(f"[WORK-TYPES] Company column not found, using fallback query")
        result = await db.execute(query)
        work_types = result.scalars().all()
        
        # work_types 테이블에서 직접 조회 (하드코딩 제거)
        
        return [
            {
                "id": wt.id,
                "name": wt.name,
                "description": wt.description,
                "is_active": wt.is_active,
                "created_at": wt.created_at.isoformat() if wt.created_at else None,
                "updated_at": wt.updated_at.isoformat() if wt.updated_at else None
            }
            for wt in work_types
        ]
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = jwt_user
        print(f"[WORK-TYPES-LIST-JWT] Request from user_id={current_user.id}, user_role={current_user.role}")
        
        try:
            # JWT 기반 작업 유형 목록 조회 (회사별 필터링 - 스키마 체크)
            user_company = current_user.company or 'default_company'

            # company 컬럼 존재 여부 확인
            from sqlalchemy import text
            check_column_query = text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'work_types' AND column_name = 'company'
            """)
            column_result = await db.execute(check_column_query)
            company_column_exists = column_result.fetchone() is not None

            if company_column_exists:
                # company 컬럼이 있는 경우 회사별 필터링
                query = select(WorkType).where(
                    WorkType.is_active == True,
                    (WorkType.company == user_company) | (WorkType.company.is_(None))
                )
                print(f"[WORK-TYPES-JWT] Using company filtering for user company: {user_company}")
            else:
                # company 컬럼이 없는 경우 fallback
                query = select(WorkType).where(WorkType.is_active == True)
                print(f"[WORK-TYPES-JWT] Company column not found, using fallback query")
            result = await db.execute(query)
            work_types = result.scalars().all()
            
            # work_types 테이블에서 직접 조회 (하드코딩 제거)
            
            print(f"[WORK-TYPES-LIST-JWT] SUCCESS: Found {len(work_types)} work types for user {current_user.id}")
            
            return [
                {
                    "id": wt.id,
                    "name": wt.name,
                    "description": wt.description,
                    "is_active": wt.is_active,
                    "created_at": wt.created_at.isoformat() if wt.created_at else None,
                    "updated_at": wt.updated_at.isoformat() if wt.updated_at else None
                }
                for wt in work_types
            ]
            
        except Exception as e:
            print(f"[WORK-TYPES-LIST-JWT] Unexpected error: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"작업 유형 조회 중 오류: {str(e)}")


@router.post("/", response_model=dict)
async def create_work_type(
    work_type_data: WorkTypeCreate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """새 작업 유형 생성"""
    print(f"[WORK-TYPE-CREATE] Creating work type: {work_type_data.dict()}")

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

        # 권한 확인 (관리자만 생성 가능)
        if user_role not in ["슈퍼 어드민", "대행사 어드민"]:
            raise HTTPException(status_code=403, detail="작업 유형 생성 권한이 없습니다")

        print(f"[WORK-TYPE-CREATE] Node.js API mode - user_id={user_id}, role={user_role}")

    else:
        # JWT 기반 모드
        current_user = jwt_user
        user_role = current_user.role.value

        # 권한 확인 (관리자만 생성 가능)
        if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
            raise HTTPException(status_code=403, detail="작업 유형 생성 권한이 없습니다")

        print(f"[WORK-TYPE-CREATE] JWT mode - user_id={current_user.id}, role={user_role}")

    try:
        # company 컬럼 존재 여부 확인
        from sqlalchemy import text
        check_column_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'work_types' AND column_name = 'company'
        """)
        column_result = await db.execute(check_column_query)
        company_column_exists = column_result.fetchone() is not None

        user_company = current_user.company or 'default_company'

        if company_column_exists:
            # 중복 이름 확인 (회사별)
            existing_query = select(WorkType).where(
                WorkType.name == work_type_data.name,
                WorkType.is_active == True,
                (WorkType.company == user_company) | (WorkType.company.is_(None))
            )
            result = await db.execute(existing_query)
            existing_work_type = result.scalar_one_or_none()

            if existing_work_type:
                raise HTTPException(status_code=400, detail="같은 회사에서 같은 이름의 작업 유형이 이미 존재합니다")

            # 새 작업 유형 생성 (회사별 자동 설정)
            new_work_type = WorkType(
                name=work_type_data.name,
                description=work_type_data.description or "",
                company=user_company,  # 생성자의 회사로 자동 설정
                is_active=True
            )
            print(f"[WORK-TYPE-CREATE] Creating with company: {user_company}")
        else:
            # company 컬럼이 없는 경우 fallback
            existing_query = select(WorkType).where(
                WorkType.name == work_type_data.name,
                WorkType.is_active == True
            )
            result = await db.execute(existing_query)
            existing_work_type = result.scalar_one_or_none()

            if existing_work_type:
                raise HTTPException(status_code=400, detail="같은 이름의 작업 유형이 이미 존재합니다")

            # 새 작업 유형 생성 (company 컬럼 없이)
            new_work_type = WorkType(
                name=work_type_data.name,
                description=work_type_data.description or "",
                is_active=True
            )
            print(f"[WORK-TYPE-CREATE] Creating without company column (fallback mode)")

        db.add(new_work_type)
        await db.commit()
        await db.refresh(new_work_type)

        print(f"[WORK-TYPE-CREATE] SUCCESS: Created work type {new_work_type.id} by user {current_user.id}")

        return {
            "id": new_work_type.id,
            "name": new_work_type.name,
            "description": new_work_type.description,
            "is_active": new_work_type.is_active,
            "created_at": new_work_type.created_at.isoformat() if new_work_type.created_at else None,
            "updated_at": new_work_type.updated_at.isoformat() if new_work_type.updated_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[WORK-TYPE-CREATE] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"작업 유형 생성 중 오류: {str(e)}")


@router.put("/{work_type_id}", response_model=dict)
async def update_work_type(
    work_type_id: int,
    work_type_data: WorkTypeUpdate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """작업 유형 수정 (이름, 설명, 활성화 상태)"""
    print(f"[WORK-TYPE-UPDATE] Updating work type {work_type_id}: {work_type_data.dict(exclude_unset=True)}")

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

        # 권한 확인 (관리자만 수정 가능)
        if user_role not in ["슈퍼 어드민", "대행사 어드민"]:
            raise HTTPException(status_code=403, detail="작업 유형 수정 권한이 없습니다")

        print(f"[WORK-TYPE-UPDATE] Node.js API mode - user_id={user_id}, role={user_role}")

    else:
        # JWT 기반 모드
        current_user = jwt_user
        user_role = current_user.role.value

        # 권한 확인 (관리자만 수정 가능)
        if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
            raise HTTPException(status_code=403, detail="작업 유형 수정 권한이 없습니다")

        print(f"[WORK-TYPE-UPDATE] JWT mode - user_id={current_user.id}, role={user_role}")

    try:
        # 작업 유형 조회 (is_active 조건 제거 - 비활성 상태도 수정 가능)
        work_type_query = select(WorkType).where(WorkType.id == work_type_id)
        result = await db.execute(work_type_query)
        work_type = result.scalar_one_or_none()

        if not work_type:
            raise HTTPException(status_code=404, detail="작업 유형을 찾을 수 없습니다")

        # 수정할 필드만 업데이트
        update_data = work_type_data.dict(exclude_unset=True)

        for field, value in update_data.items():
            if hasattr(work_type, field):
                setattr(work_type, field, value)
                print(f"[WORK-TYPE-UPDATE] Updated {field}: {value}")

        await db.commit()
        await db.refresh(work_type)

        print(f"[WORK-TYPE-UPDATE] SUCCESS: Updated work type {work_type_id} by user {current_user.id}")

        return {
            "id": work_type.id,
            "name": work_type.name,
            "description": work_type.description,
            "is_active": work_type.is_active,
            "created_at": work_type.created_at.isoformat() if work_type.created_at else None,
            "updated_at": work_type.updated_at.isoformat() if work_type.updated_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[WORK-TYPE-UPDATE] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"작업 유형 수정 중 오류: {str(e)}")


@router.delete("/{work_type_id}", status_code=204)
async def delete_work_type(
    work_type_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """작업 유형 삭제 (소프트 삭제 - is_active를 False로 변경)"""
    print(f"[WORK-TYPE-DELETE] Deleting work type: {work_type_id}")

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

        # 권한 확인 (관리자만 삭제 가능)
        if user_role not in ["슈퍼 어드민", "대행사 어드민"]:
            raise HTTPException(status_code=403, detail="작업 유형 삭제 권한이 없습니다")

        print(f"[WORK-TYPE-DELETE] Node.js API mode - user_id={user_id}, role={user_role}")

    else:
        # JWT 기반 모드
        current_user = jwt_user
        user_role = current_user.role.value

        # 권한 확인 (관리자만 삭제 가능)
        if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
            raise HTTPException(status_code=403, detail="작업 유형 삭제 권한이 없습니다")

        print(f"[WORK-TYPE-DELETE] JWT mode - user_id={current_user.id}, role={user_role}")

    try:
        # 작업 유형 조회
        work_type_query = select(WorkType).where(WorkType.id == work_type_id, WorkType.is_active == True)
        result = await db.execute(work_type_query)
        work_type = result.scalar_one_or_none()

        if not work_type:
            raise HTTPException(status_code=404, detail="작업 유형을 찾을 수 없습니다")

        # 소프트 삭제 (is_active를 False로 변경)
        work_type.is_active = False

        await db.commit()

        print(f"[WORK-TYPE-DELETE] SUCCESS: Soft deleted work type {work_type_id} by user {current_user.id}")

        # 204 No Content 응답 (body 없음)
        return

    except HTTPException:
        raise
    except Exception as e:
        print(f"[WORK-TYPE-DELETE] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"작업 유형 삭제 중 오류: {str(e)}")