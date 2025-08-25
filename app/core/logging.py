"""
Secure logging system for BrandFlow API
민감한 정보 로깅 방지 및 보안 로깅
"""

import logging
import re
import json
from typing import Any, Dict, Optional, List
from datetime import datetime
import hashlib


class SecureFormatter(logging.Formatter):
    """민감한 정보를 마스킹하는 로그 포매터"""
    
    # 민감한 정보 패턴들
    SENSITIVE_PATTERNS = [
        # 패스워드 관련
        (r'(?i)(password|pwd|passwd)["\s]*[:=]["\s]*([^",\s]+)', r'\1": "***"'),
        (r'(?i)(password|pwd|passwd)=([^&\s]+)', r'\1=***'),
        
        # JWT 토큰
        (r'(?i)(token|jwt|bearer)["\s]*[:=]["\s]*([A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)', r'\1": "***"'),
        (r'(?i)bearer\s+([A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)', r'Bearer ***'),
        
        # API 키
        (r'(?i)(api[_-]?key|apikey|key)["\s]*[:=]["\s]*([^",\s]+)', r'\1": "***"'),
        
        # 이메일 (부분 마스킹)
        (r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', lambda m: self._mask_email(m.group(1))),
        
        # 전화번호
        (r'(?i)(phone|tel|mobile)["\s]*[:=]["\s]*([0-9\-\+\(\)\s]+)', r'\1": "***"'),
        (r'\b(\d{2,3}[-.\s]?\d{3,4}[-.\s]?\d{4})\b', r'***-****-****'),
        
        # 신용카드 번호
        (r'\b(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})\b', r'****-****-****-****'),
        
        # 사업자등록번호
        (r'\b(\d{3}[-]?\d{2}[-]?\d{5})\b', r'***-**-*****'),
    ]
    
    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 포맷하고 민감한 정보를 마스킹"""
        # 기본 포맷팅
        formatted = super().format(record)
        
        # 민감한 정보 마스킹
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            if callable(replacement):
                formatted = re.sub(pattern, replacement, formatted)
            else:
                formatted = re.sub(pattern, replacement, formatted)
        
        return formatted
    
    def _mask_email(self, email: str) -> str:
        """이메일 부분 마스킹"""
        try:
            local, domain = email.split('@')
            if len(local) <= 2:
                masked_local = '*' * len(local)
            else:
                masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
            return f"{masked_local}@{domain}"
        except:
            return "***@***.***"


class SecurityLogger:
    """보안 이벤트 전용 로거"""
    
    def __init__(self):
        self.logger = logging.getLogger("brandflow.security")
        self.logger.setLevel(logging.INFO)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            SecureFormatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )
        self.logger.addHandler(console_handler)
    
    def log_login_attempt(self, email: str, success: bool, ip: str, user_agent: str = ""):
        """로그인 시도 기록"""
        event_data = {
            "event_type": "login_attempt",
            "email": email,  # 포매터가 마스킹할 것
            "success": success,
            "ip": ip,
            "user_agent": user_agent[:100],  # 100자로 제한
            "timestamp": datetime.utcnow().isoformat()
        }
        
        level = logging.INFO if success else logging.WARNING
        self.logger.log(level, f"Login attempt: {json.dumps(event_data)}")
    
    def log_password_change(self, user_id: str, ip: str):
        """패스워드 변경 기록"""
        event_data = {
            "event_type": "password_change",
            "user_id": user_id,
            "ip": ip,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.info(f"Password change: {json.dumps(event_data)}")
    
    def log_suspicious_activity(self, event_type: str, details: Dict[str, Any], ip: str):
        """의심스러운 활동 기록"""
        event_data = {
            "event_type": "suspicious_activity",
            "activity": event_type,
            "details": details,
            "ip": ip,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.warning(f"Suspicious activity: {json.dumps(event_data)}")
    
    def log_permission_denied(self, user_id: str, resource: str, action: str, ip: str):
        """권한 거부 기록"""
        event_data = {
            "event_type": "permission_denied",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "ip": ip,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.warning(f"Permission denied: {json.dumps(event_data)}")
    
    def log_data_access(self, user_id: str, resource: str, action: str, record_count: int = 0):
        """데이터 접근 기록"""
        event_data = {
            "event_type": "data_access",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "record_count": record_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.info(f"Data access: {json.dumps(event_data)}")


def sanitize_log_data(data: Any) -> Any:
    """로깅용 데이터 정화"""
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # 민감한 키 체크
            if any(sensitive in key.lower() for sensitive in [
                'password', 'passwd', 'pwd', 'token', 'key', 'secret', 
                'authorization', 'auth', 'credential'
            ]):
                sanitized[key] = "***"
            else:
                sanitized[key] = sanitize_log_data(value)
        return sanitized
    
    elif isinstance(data, (list, tuple)):
        return [sanitize_log_data(item) for item in data]
    
    elif isinstance(data, str):
        # 문자열에서 민감한 패턴 찾아서 마스킹
        # JWT 토큰 패턴
        if re.match(r'^[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+$', data):
            return "***"
        
        # 이메일 패턴
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', data):
            return "***@***.***"
        
        return data
    
    else:
        return data


def hash_pii(data: str) -> str:
    """개인정보 해싱 (로깅용)"""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]


# 전역 보안 로거 인스턴스
security_logger = SecurityLogger()


# 애플리케이션 로거 설정
def setup_application_logging():
    """애플리케이션 로깅 설정"""
    # 루트 로거 설정
    root_logger = logging.getLogger("brandflow")
    root_logger.setLevel(logging.INFO)
    
    # 콘솔 핸들러 (개발용)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        SecureFormatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
    )
    root_logger.addHandler(console_handler)
    
    # SQLAlchemy 로거 설정 (민감한 정보 포함 가능)
    sql_logger = logging.getLogger("sqlalchemy.engine")
    sql_logger.setLevel(logging.WARNING)  # SQL 쿼리 로그 비활성화
    
    return root_logger


# 로깅 데코레이터
def log_api_call(func):
    """API 호출 로깅 데코레이터"""
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger("brandflow.api")
        
        try:
            # 함수 호출 시작 로깅
            sanitized_kwargs = sanitize_log_data(kwargs)
            logger.info(f"API call started: {func.__name__} with args: {sanitized_kwargs}")
            
            result = await func(*args, **kwargs)
            
            # 성공 로깅
            logger.info(f"API call completed: {func.__name__}")
            return result
            
        except Exception as e:
            # 에러 로깅
            logger.error(f"API call failed: {func.__name__} - {str(e)}")
            raise
    
    return wrapper