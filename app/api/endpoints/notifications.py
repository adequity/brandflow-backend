from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from urllib.parse import unquote
from pydantic import BaseModel

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.core.cache import cached

router = APIRouter()


def map_english_role_to_korean(user_role: str) -> str:
    """영어 역할명을 한글로 매핑 (프론트엔드 호환성)"""
    english_to_korean_roles = {
        'super_admin': '슈퍼 어드민',
        'agency_admin': '대행사 어드민',
        'agency_staff': '대행사 직원',
        'staff': '직원',
        'client': '클라이언트',
        'admin': '어드민'
    }
    
    # 영어 역할명이면 한글로 변환
    if user_role in english_to_korean_roles:
        return english_to_korean_roles[user_role]
    return user_role


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
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """읽지 않은 알림 개수 조회"""
    print(f"[NOTIFICATIONS] unread-count request: viewerId={viewerId}, viewerRole={viewerRole}")
    
    try:
        # Node.js API 호환 모드인지 확인
        if viewerId is not None or adminId is not None:
            # Node.js API 호환 모드
            user_id = viewerId or adminId
            user_role = viewerRole or adminRole
            
            if not user_id or not user_role:
                print(f"[NOTIFICATIONS] ERROR: Missing params - user_id={user_id}, user_role={user_role}")
                raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
            
            # URL 디코딩 및 역할명 매핑
            user_role = unquote(user_role).strip()
            user_role = map_english_role_to_korean(user_role)
            print(f"[NOTIFICATIONS] Processing user_id={user_id}, user_role='{user_role}'")
            
            # 캐시된 사용자 조회
            current_user = await get_user_from_db_cached(user_id, db)
            
            if not current_user:
                print(f"[NOTIFICATIONS] ERROR: User not found - user_id={user_id}")
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
            
            print(f"[NOTIFICATIONS] Found user: {current_user.name}")
            
            # 캐시된 알림 개수 조회
            result = await get_unread_count_cached(user_id, user_role)
            print(f"[NOTIFICATIONS] SUCCESS: Returning {result}")
            return result
        else:
            # 기존 API 모드 (JWT 토큰 기반)
            current_user = jwt_user
            print(f"[NOTIFICATIONS-UNREAD-COUNT-JWT] Request from user_id={current_user.id}, user_role={current_user.role}")
            
            try:
                # JWT 기반 알림 개수 조회
                user_role = current_user.role.value
                result = await get_unread_count_cached(current_user.id, user_role)
                
                print(f"[NOTIFICATIONS-UNREAD-COUNT-JWT] SUCCESS: Returning {result} for user {current_user.id}")
                return result
                
            except Exception as e:
                print(f"[NOTIFICATIONS-UNREAD-COUNT-JWT] Unexpected error: {type(e).__name__}: {e}")
                # 오류 시 기본값 반환
                return {"unread_count": 0}
    except Exception as e:
        print(f"[NOTIFICATIONS] Unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"알림 조회 중 오류: {str(e)}")


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
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """알림 목록 조회"""
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩 및 역할명 매핑
        user_role = unquote(user_role).strip()
        user_role = map_english_role_to_korean(user_role)
        
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
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = jwt_user
        print(f"[NOTIFICATIONS-LIST-JWT] Request from user_id={current_user.id}, user_role={current_user.role}")
        
        try:
            # JWT 기반 알림 목록 조회
            # 현재는 빈 목록 반환 (실제 알림 시스템 구현 시 DB에서 조회)
            notifications = []
            
            print(f"[NOTIFICATIONS-LIST-JWT] SUCCESS: Returning {len(notifications)} notifications for user {current_user.id}")
            
            return NotificationsListResponse(
                notifications=notifications,
                unreadCount=0,
                total=0
            )
            
        except Exception as e:
            print(f"[NOTIFICATIONS-LIST-JWT] Unexpected error: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"알림 조회 중 오류: {str(e)}")


@router.put("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """알림을 읽음으로 표시"""
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩 및 역할명 매핑
        user_role = unquote(user_role).strip()
        user_role = map_english_role_to_korean(user_role)
        
        # 캐시된 사용자 조회
        current_user = await get_user_from_db_cached(user_id, db)
        
        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 현재는 성공 응답만 반환 (실제 알림 시스템 구현 시 DB 업데이트)
        return {"message": "알림이 읽음으로 표시되었습니다", "notificationId": notification_id}
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = jwt_user
        print(f"[NOTIFICATIONS-MARK-READ-JWT] Request from user_id={current_user.id}, notification_id={notification_id}")
        
        try:
            # JWT 기반 알림 읽음 처리
            # 현재는 성공 응답만 반환 (실제 알림 시스템 구현 시 DB 업데이트)
            
            print(f"[NOTIFICATIONS-MARK-READ-JWT] SUCCESS: Marked notification {notification_id} as read for user {current_user.id}")
            return {"message": "알림이 읽음으로 표시되었습니다", "notificationId": notification_id}
            
        except Exception as e:
            print(f"[NOTIFICATIONS-MARK-READ-JWT] Unexpected error: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"알림 업데이트 중 오류: {str(e)}")


@router.put("/read-all")
async def mark_all_notifications_as_read(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """모든 알림을 읽음으로 표시"""
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩 및 역할명 매핑
        user_role = unquote(user_role).strip()
        user_role = map_english_role_to_korean(user_role)
        
        # 캐시된 사용자 조회
        current_user = await get_user_from_db_cached(user_id, db)
        
        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 현재는 성공 응답만 반환 (실제 알림 시스템 구현 시 DB에서 모든 알림 업데이트)
        return {"message": "모든 알림이 읽음으로 표시되었습니다", "updatedCount": 0}
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = jwt_user
        print(f"[NOTIFICATIONS-MARK-ALL-READ-JWT] Request from user_id={current_user.id}")
        
        try:
            # JWT 기반 모든 알림 읽음 처리
            # 현재는 성공 응답만 반환 (실제 알림 시스템 구현 시 DB에서 모든 알림 업데이트)
            
            print(f"[NOTIFICATIONS-MARK-ALL-READ-JWT] SUCCESS: Marked all notifications as read for user {current_user.id}")
            return {"message": "모든 알림이 읽음으로 표시되었습니다", "updatedCount": 0}
            
        except Exception as e:
            print(f"[NOTIFICATIONS-MARK-ALL-READ-JWT] Unexpected error: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"알림 업데이트 중 오류: {str(e)}")