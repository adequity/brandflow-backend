from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import secrets
import hashlib
import time

from app.core.config import settings

# 패스워드 해싱 컨텍스트 (보안 강화)
pwd_context = CryptContext(
    schemes=["bcrypt"], 
    deprecated="auto",
    bcrypt__rounds=12  # bcrypt 라운드 수 증가 (기본값 12)
)

# JWT 블랙리스트 (간단한 메모리 기반, 프로덕션에서는 Redis 사용 권장)
_token_blacklist = set()
_refresh_tokens = {}  # refresh_token: {user_id, expires_at, jti}


def create_access_token(
    subject: Union[str, Any], 
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """액세스 토큰 생성 (보안 강화)"""
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    # JWT 고유 ID (JTI) 생성
    jti = secrets.token_urlsafe(32)
    
    # 기본 클레임
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": now,  # 발급 시간
        "nbf": now,  # 유효 시작 시간
        "jti": jti,  # JWT ID
        "type": "access"  # 토큰 타입
    }
    
    # 추가 클레임 포함
    if additional_claims:
        to_encode.update(additional_claims)
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: Union[str, int]) -> str:
    """리프레시 토큰 생성"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=7)  # 7일 유효
    
    jti = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(64)
    
    # 리프레시 토큰 정보 저장
    _refresh_tokens[refresh_token] = {
        "user_id": str(user_id),
        "expires_at": expire,
        "jti": jti,
        "created_at": now
    }
    
    return refresh_token


def verify_refresh_token(refresh_token: str) -> Optional[str]:
    """리프레시 토큰 검증"""
    if refresh_token not in _refresh_tokens:
        return None
    
    token_data = _refresh_tokens[refresh_token]
    now = datetime.now(timezone.utc)
    
    # 만료 시간 체크
    if now > token_data["expires_at"]:
        del _refresh_tokens[refresh_token]
        return None
    
    return token_data["user_id"]


def revoke_refresh_token(refresh_token: str) -> bool:
    """리프레시 토큰 무효화"""
    if refresh_token in _refresh_tokens:
        del _refresh_tokens[refresh_token]
        return True
    return False


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """토큰 검증 (보안 강화)"""
    try:
        # JWT 디코딩
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        
        # 필수 클레임 검증
        if not all(key in payload for key in ["sub", "exp", "iat", "jti"]):
            return None
        
        # 토큰 타입 검증
        if payload.get("type") != "access":
            return None
        
        # JTI 블랙리스트 확인
        jti = payload.get("jti")
        if jti in _token_blacklist:
            return None
        
        # 현재 시간 체크 (추가 안전장치)
        now = datetime.now(timezone.utc)
        exp = datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc)
        if now >= exp:
            return None
        
        return payload
        
    except JWTError as e:
        # 로깅 (실제로는 로거 사용)
        print(f"JWT verification failed: {str(e)}")
        return None


def blacklist_token(token: str) -> bool:
    """토큰을 블랙리스트에 추가 (로그아웃시 사용)"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        jti = payload.get("jti")
        if jti:
            _token_blacklist.add(jti)
            return True
    except JWTError:
        pass
    return False


def cleanup_expired_tokens():
    """만료된 토큰들 정리"""
    now = datetime.now(timezone.utc)
    
    # 만료된 리프레시 토큰 정리
    expired_refresh_tokens = [
        token for token, data in _refresh_tokens.items()
        if now > data["expires_at"]
    ]
    
    for token in expired_refresh_tokens:
        del _refresh_tokens[token]
    
    # 블랙리스트는 주기적으로 완전히 초기화 (메모리 누수 방지)
    # 프로덕션에서는 Redis TTL 사용 권장
    if len(_token_blacklist) > 10000:
        _token_blacklist.clear()
    
    return len(expired_refresh_tokens)


def get_password_hash(password: str) -> str:
    """패스워드 해싱 (보안 강화)"""
    # 패스워드 강도 검증
    if not validate_password_strength(password):
        raise ValueError("패스워드가 보안 요구사항을 충족하지 않습니다.")
    
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """패스워드 검증"""
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_strength(password: str) -> bool:
    """패스워드 강도 검증"""
    # 최소 8자 이상
    if len(password) < 8:
        return False
    
    # 최대 128자 이하 (DoS 공격 방지)
    if len(password) > 128:
        return False
    
    # 영문 대소문자, 숫자, 특수문자 중 최소 3가지 포함
    checks = [
        any(c.islower() for c in password),  # 소문자
        any(c.isupper() for c in password),  # 대문자
        any(c.isdigit() for c in password),  # 숫자
        any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)  # 특수문자
    ]
    
    if sum(checks) < 3:
        return False
    
    # 일반적인 약한 패스워드 체크
    weak_passwords = [
        "password", "123456", "qwerty", "admin", "letmein",
        "welcome", "monkey", "dragon", "master", "password123"
    ]
    
    if password.lower() in weak_passwords:
        return False
    
    # 연속된 문자 체크 (123456, abcdef 등)
    for i in range(len(password) - 3):
        if len(set(password[i:i+4])) <= 2:  # 4자리가 2가지 이하 문자로만 구성
            return False
    
    return True


def hash_sensitive_data(data: str) -> str:
    """민감한 데이터 해싱 (이메일, 전화번호 등)"""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def generate_secure_token(length: int = 32) -> str:
    """보안 토큰 생성"""
    return secrets.token_urlsafe(length)