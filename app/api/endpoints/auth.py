from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app.db.database import get_async_db
from app.schemas.user import UserLogin, Token, UserResponse
from app.services.user_service import UserService
from app.core.security import create_access_token, verify_password, create_refresh_token, blacklist_token
from app.core.config import settings
from app.core.logging import security_logger

router = APIRouter()


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


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_db)
):
    """사용자 로그인"""
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    
    service = UserService(db)
    user = await service.get_user_by_email(form_data.username)
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        security_logger.log_login_attempt(
            email=form_data.username,
            success=False,
            ip=client_ip,
            user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        security_logger.log_login_attempt(
            email=form_data.username,
            success=False,
            ip=client_ip,
            user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비활성화된 계정입니다."
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )
    
    security_logger.log_login_attempt(
        email=form_data.username,
        success=True,
        ip=client_ip,
        user_agent=user_agent
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )


@router.post("/login-json", response_model=Token)
async def login_json(
    request: Request,
    login_data: UserLogin,
    db: AsyncSession = Depends(get_async_db)
):
    """JSON 형태 로그인"""
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    
    service = UserService(db)
    user = await service.get_user_by_email(login_data.email)
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        security_logger.log_login_attempt(
            email=login_data.email,
            success=False,
            ip=client_ip,
            user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )
    
    if not user.is_active:
        security_logger.log_login_attempt(
            email=login_data.email,
            success=False,
            ip=client_ip,
            user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비활성화된 계정입니다."
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )
    
    security_logger.log_login_attempt(
        email=login_data.email,
        success=True,
        ip=client_ip,
        user_agent=user_agent
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )


@router.post("/logout")
async def logout(
    request: Request,
    token: str = Depends(lambda request: request.headers.get("Authorization", "").replace("Bearer ", ""))
):
    """로그아웃 및 토큰 블랙리스트 처리"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 필요합니다."
        )
    
    try:
        blacklist_token(token)
        return {"message": "로그아웃되었습니다."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="로그아웃 처리 중 오류가 발생했습니다."
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    refresh_token: str = Depends(lambda request: request.headers.get("X-Refresh-Token", ""))
):
    """리프레시 토큰을 사용한 액세스 토큰 갱신"""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="리프레시 토큰이 필요합니다."
        )
    
    # TODO: 리프레시 토큰 검증 로직 구현 필요
    # 현재는 기본 응답만 반환
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="리프레시 토큰 기능은 구현 예정입니다."
    )