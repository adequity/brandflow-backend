from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from urllib.parse import unquote
from pydantic import BaseModel

from app.db.database import get_async_db
from app.models.user import User
from app.core.cache import cached

router = APIRouter()


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str = "info"
    isRead: bool = False
    createdAt: str
    readAt: Optional[str] = None


class NotificationsListResponse(BaseModel):
    notifications: List[NotificationResponse]
    unreadCount: int
    total: int


async def get_user_from_db_cached(user_id: int, db: AsyncSession) -> Optional[User]:
    """사용자 정보 조회 (캐시됨 - 30초)"""
    
    # 캐시 키 생성 (user_id만 사용)
    cache_key = f"user_lookup_{user_id}"
    
    # 캐시에서 조회
    from app.core.cache import app_cache
    cached_user = await app_cache.get(cache_key)
    if cached_user is not None:
        return cached_user
    
    # 캐시 미스 - DB에서 조회
    current_user_query = select(User).where(User.id == user_id)
    result = await db.execute(current_user_query)
    user = result.scalar_one_or_none()
    
    # 결과 캐싱 (30초)
    await app_cache.set(cache_key, user, ttl=30)
    
    return user


@cached(ttl=60, key_prefix="unread_count_")
async def get_unread_count_cached(user_id: int, user_role: str) -> dict:
    """알림 개수 조회 (캐시됨 - 1분)"""
    # 현재는 하드코딩된 값 반환
    # 실제 알림 시스템이 구현되면 여기서 DB 조회
    return {"unread_count": 0}


@router.get("/unread-count")
async def get_unread_notifications_count(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """읽지 않은 알림 개수 조회"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 캐시된 사용자 조회
        current_user = await get_user_from_db_cached(user_id, db)
        
        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 캐시된 알림 개수 조회
        return await get_unread_count_cached(user_id, user_role)
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        # TODO: JWT 토큰 기반 인증 구현
        return {"unread_count": 0}


@router.get("/")
async def get_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unreadOnly: bool = Query(False),
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """알림 목록 조회"""
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 캐시된 사용자 조회
        current_user = await get_user_from_db_cached(user_id, db)
        
        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    
    # 현재는 빈 알림 목록 반환 (실제 알림 시스템 구현 시 DB에서 조회)
    notifications = []
    
    return NotificationsListResponse(
        notifications=notifications,
        unreadCount=0,
        total=0
    )


@router.put("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """알림을 읽음으로 표시"""
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 캐시된 사용자 조회
        current_user = await get_user_from_db_cached(user_id, db)
        
        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    
    # 현재는 성공 응답만 반환 (실제 알림 시스템 구현 시 DB 업데이트)
    return {"message": "알림이 읽음으로 표시되었습니다", "notificationId": notification_id}


@router.put("/read-all")
async def mark_all_notifications_as_read(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """모든 알림을 읽음으로 표시"""
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 캐시된 사용자 조회
        current_user = await get_user_from_db_cached(user_id, db)
        
        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    
    # 현재는 성공 응답만 반환 (실제 알림 시스템 구현 시 DB에서 모든 알림 업데이트)
    return {"message": "모든 알림이 읽음으로 표시되었습니다", "updatedCount": 0}