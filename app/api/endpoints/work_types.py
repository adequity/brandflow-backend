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
        
        # 작업 유형 조회 (Node.js API 모드)
        query = select(WorkType).where(WorkType.is_active == True)
        result = await db.execute(query)
        work_types = result.scalars().all()
        
        # 기본 작업 유형이 없으면 생성
        if not work_types:
            default_types = [
                {"name": "블로그 포스트", "description": "블로그 콘텐츠 작성"},
                {"name": "인스타그램 포스트", "description": "인스타그램 콘텐츠 제작"},
                {"name": "유튜브 영상", "description": "유튜브 동영상 제작"},
                {"name": "페이스북 광고", "description": "페이스북 광고 콘텐츠"},
                {"name": "카카오 채널", "description": "카카오톡 채널 운영"},
                {"name": "네이버 블로그", "description": "네이버 블로그 포스팅"},
                {"name": "기타", "description": "기타 마케팅 업무"}
            ]
            
            for type_data in default_types:
                work_type = WorkType(**type_data)
                db.add(work_type)
            
            await db.commit()
            
            # 새로 생성된 작업 유형 조회
            result = await db.execute(query)
            work_types = result.scalars().all()
        
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
            # JWT 기반 작업 유형 목록 조회 (모든 역할이 조회 가능)
            query = select(WorkType).where(WorkType.is_active == True)
            result = await db.execute(query)
            work_types = result.scalars().all()
            
            # 기본 작업 유형이 없으면 생성
            if not work_types:
                default_types = [
                    {"name": "블로그 포스트", "description": "블로그 콘텐츠 작성"},
                    {"name": "인스타그램 포스트", "description": "인스타그램 콘텐츠 제작"},
                    {"name": "유튜브 영상", "description": "유튜브 동영상 제작"},
                    {"name": "페이스북 광고", "description": "페이스북 광고 콘텐츠"},
                    {"name": "카카오 채널", "description": "카카오톡 채널 운영"},
                    {"name": "네이버 블로그", "description": "네이버 블로그 포스팅"},
                    {"name": "기타", "description": "기타 마케팅 업무"}
                ]
                
                for type_data in default_types:
                    work_type = WorkType(**type_data)
                    db.add(work_type)
                
                await db.commit()
                
                # 새로 생성된 작업 유형 조회
                result = await db.execute(query)
                work_types = result.scalars().all()
            
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
        # 중복 이름 확인
        existing_query = select(WorkType).where(WorkType.name == work_type_data.name, WorkType.is_active == True)
        result = await db.execute(existing_query)
        existing_work_type = result.scalar_one_or_none()

        if existing_work_type:
            raise HTTPException(status_code=400, detail="같은 이름의 작업 유형이 이미 존재합니다")

        # 새 작업 유형 생성
        new_work_type = WorkType(
            name=work_type_data.name,
            description=work_type_data.description or "",
            is_active=True
        )

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