"""
API 의존성 모듈
공통 의존성 함수들을 정의
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_async_db
from app.models.user import User
from app.core.auth import decode_access_token
from app.db.crud import get_user_by_id

# Bearer 토큰 스키마
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_async_db)
) -> Optional[User]:
    """현재 사용자 정보 조회"""
    try:
        # 토큰에서 사용자 ID 추출
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 사용자 정보 조회
        user = await get_user_by_id(db, int(user_id))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return user
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """활성화된 현재 사용자 정보 조회"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """관리자 권한 사용자 확인"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user