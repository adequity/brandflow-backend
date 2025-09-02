from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from urllib.parse import unquote

from app.db.database import get_async_db
from app.models.user import User
from app.models.work_type import WorkType

router = APIRouter()


@router.get("/", response_model=List[dict])
async def get_work_types(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
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
    
    # 작업 유형 조회
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