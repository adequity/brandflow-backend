from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import time

from app.db.database import get_async_db
from app.core.security import verify_token
from app.services.user_service import UserService
from app.models.user import User, UserRole
from app.core.logging import security_logger

security = HTTPBearer(auto_error=True)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_db)
) -> User:
    """현재 사용자 조회 (보안 강화)"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보를 확인할 수 없습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # JWT 토큰 검증 (강화된 검증)
        token_payload = verify_token(credentials.credentials)
        if token_payload is None:
            security_logger.log_suspicious_activity(
                "invalid_token_access",
                {"token_length": len(credentials.credentials)},
                _get_client_ip(request)
            )
            raise credentials_exception
        
        # 사용자 식별자 추출 (ID 또는 이메일)
        user_identifier = token_payload.get("sub")
        if not user_identifier:
            raise credentials_exception
        
        # 사용자 조회 (JWT subject는 이제 항상 user ID)
        service = UserService(db)
        try:
            # JWT subject는 이제 항상 user ID (문자열)
            user_id = int(user_identifier)
            user = await service.get_user_by_id(user_id)
        except ValueError:
            # 혹시 이전 토큰이 이메일을 담고 있는 경우 호환성 유지
            user = await service.get_user_by_email(user_identifier)
        if user is None:
            security_logger.log_suspicious_activity(
                "nonexistent_user_token",
                {"user_identifier": user_identifier},
                _get_client_ip(request)
            )
            raise credentials_exception
        
        # 사용자 상태 확인
        if not user.is_active:
            security_logger.log_suspicious_activity(
                "inactive_user_access",
                {"user_identifier": user_identifier},
                _get_client_ip(request)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="비활성화된 사용자입니다."
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        security_logger.log_suspicious_activity(
            "authentication_error",
            {"error": str(e)},
            _get_client_ip(request)
        )
        raise credentials_exception


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """현재 활성 사용자 조회 (이미 get_current_user에서 체크됨)"""
    return current_user


def require_roles(allowed_roles: List[UserRole]):
    """특정 역할을 요구하는 의존성"""
    def role_checker(
        request: Request,
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.role not in allowed_roles:
            security_logger.log_permission_denied(
                str(current_user.id),
                "role_restricted_endpoint",
                f"required: {allowed_roles}, actual: {current_user.role}",
                _get_client_ip(request)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"권한이 부족합니다. 필요한 권한: {[role.value for role in allowed_roles]}"
            )
        return current_user
    return role_checker


def require_admin_access():
    """관리자 권한 요구"""
    return require_roles([UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN])


def require_super_admin():
    """슈퍼 관리자 권한 요구"""
    return require_roles([UserRole.SUPER_ADMIN])


async def get_optional_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_async_db)
) -> Optional[User]:
    """선택적 사용자 인증 (토큰이 없어도 허용)"""
    if credentials is None:
        return None
    
    try:
        token_payload = verify_token(credentials.credentials)
        if token_payload is None:
            return None
        
        user_identifier = token_payload.get("sub")
        if not user_identifier:
            return None
        
        service = UserService(db)
        try:
            # JWT subject는 이제 항상 user ID (문자열)
            user_id = int(user_identifier)
            user = await service.get_user_by_id(user_id)
        except ValueError:
            # 혹시 이전 토큰이 이메일을 담고 있는 경우 호환성 유지
            user = await service.get_user_by_email(user_identifier)
        
        if user and user.is_active:
            return user
        
        return None
        
    except Exception:
        return None


def _get_client_ip(request: Request) -> str:
    """클라이언트 IP 주소 추출"""
    # X-Forwarded-For 헤더 확인 (프록시/로드밸런서 사용시)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    # X-Real-IP 헤더 확인
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # 기본 클라이언트 IP
    return request.client.host if request.client else "unknown"