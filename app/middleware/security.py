"""
Security middleware for BrandFlow API
보안 헤더 및 보안 정책 적용
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable
import secrets


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """보안 헤더를 추가하는 미들웨어"""
    
    def __init__(self, app, **kwargs):
        super().__init__(app)
        # CSP nonce 생성용
        self.generate_nonce = kwargs.get('generate_nonce', True)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # CSP nonce 생성
        nonce = secrets.token_urlsafe(16) if self.generate_nonce else None
        
        # 보안 헤더 추가
        security_headers = {
            # XSS 보호
            "X-XSS-Protection": "1; mode=block",
            
            # Content Type Sniffing 방지
            "X-Content-Type-Options": "nosniff",
            
            # Clickjacking 방지 (API이므로 DENY)
            "X-Frame-Options": "DENY",
            
            # Referrer 정책
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Content Security Policy (API 전용)
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self'; "
                "font-src 'self'; "
                "object-src 'none'; "
                "media-src 'self'; "
                "frame-src 'none'; "
                f"{'script-src ' + repr('nonce-' + nonce) + '; ' if nonce else ''}"
                "base-uri 'self';"
            ),
            
            # HSTS (프로덕션에서 HTTPS 사용시)
            # "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            
            # 권한 정책 (불필요한 기능 비활성화)
            "Permissions-Policy": (
                "accelerometer=(), "
                "ambient-light-sensor=(), "
                "autoplay=(), "
                "battery=(), "
                "camera=(), "
                "cross-origin-isolated=(), "
                "display-capture=(), "
                "document-domain=(), "
                "encrypted-media=(), "
                "execution-while-not-rendered=(), "
                "execution-while-out-of-viewport=(), "
                "fullscreen=(), "
                "geolocation=(), "
                "gyroscope=(), "
                "magnetometer=(), "
                "microphone=(), "
                "midi=(), "
                "navigation-override=(), "
                "payment=(), "
                "picture-in-picture=(), "
                "publickey-credentials-get=(), "
                "screen-wake-lock=(), "
                "sync-xhr=(), "
                "usb=(), "
                "web-share=(), "
                "xr-spatial-tracking=()"
            ),
            
            # API 서버 식별 제거
            "Server": "BrandFlow-API"
        }
        
        # 헤더 적용
        for header_name, header_value in security_headers.items():
            response.headers[header_name] = header_value
        
        # nonce를 응답에 추가 (필요시)
        if nonce:
            response.headers["X-CSP-Nonce"] = nonce
            
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """간단한 레이트 리미팅 미들웨어"""
    
    def __init__(self, app, **kwargs):
        super().__init__(app)
        self.requests_per_minute = kwargs.get('requests_per_minute', 100)
        self.requests_per_second = kwargs.get('requests_per_second', 10)
        # 메모리 기반 간단한 레이트 리미터 (프로덕션에서는 Redis 사용 권장)
        self.client_requests = {}
        import time
        self.time = time
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from fastapi import HTTPException, status
        
        # 클라이언트 IP 가져오기
        client_ip = self._get_client_ip(request)
        current_time = self.time.time()
        
        # 클라이언트별 요청 기록 초기화
        if client_ip not in self.client_requests:
            self.client_requests[client_ip] = {
                'minute_requests': [],
                'second_requests': []
            }
        
        client_data = self.client_requests[client_ip]
        
        # 1분 이전 요청 제거
        client_data['minute_requests'] = [
            req_time for req_time in client_data['minute_requests']
            if current_time - req_time < 60
        ]
        
        # 1초 이전 요청 제거
        client_data['second_requests'] = [
            req_time for req_time in client_data['second_requests']
            if current_time - req_time < 1
        ]
        
        # 레이트 리밋 체크
        if len(client_data['minute_requests']) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="분당 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
            )
        
        if len(client_data['second_requests']) >= self.requests_per_second:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="초당 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
            )
        
        # 현재 요청 기록
        client_data['minute_requests'].append(current_time)
        client_data['second_requests'].append(current_time)
        
        response = await call_next(request)
        
        # 레이트 리밋 정보를 헤더에 추가
        response.headers["X-RateLimit-Minute-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Minute-Remaining"] = str(
            self.requests_per_minute - len(client_data['minute_requests'])
        )
        response.headers["X-RateLimit-Second-Limit"] = str(self.requests_per_second)
        response.headers["X-RateLimit-Second-Remaining"] = str(
            self.requests_per_second - len(client_data['second_requests'])
        )
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 주소 추출"""
        # X-Forwarded-For 헤더 확인 (프록시/로드밸런서 사용시)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # 첫 번째 IP가 실제 클라이언트 IP
            return forwarded_for.split(",")[0].strip()
        
        # X-Real-IP 헤더 확인
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 기본 클라이언트 IP
        return request.client.host if request.client else "unknown"


class RequestSanitizationMiddleware(BaseHTTPMiddleware):
    """요청 데이터 검증 및 정화 미들웨어"""
    
    def __init__(self, app, **kwargs):
        super().__init__(app)
        self.max_body_size = kwargs.get('max_body_size', 10 * 1024 * 1024)  # 10MB
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from fastapi import HTTPException, status
        
        # Content-Length 체크
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"요청 크기가 너무 큽니다. 최대 {self.max_body_size // (1024*1024)}MB까지 허용됩니다."
            )
        
        # 의심스러운 헤더 체크
        suspicious_headers = [
            "x-forwarded-host",
            "x-forwarded-server", 
            "x-forwarded-proto"
        ]
        
        for header in suspicious_headers:
            if header in request.headers:
                # 로깅 (실제로는 로거 사용)
                print(f"Suspicious header detected: {header} = {request.headers[header]}")
        
        response = await call_next(request)
        return response