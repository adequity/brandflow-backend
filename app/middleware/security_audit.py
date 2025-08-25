"""
통합 보안 감사 미들웨어
- 요청별 보안 스캔
- 실시간 위협 감지
- 자동 감사 로깅
- 의심스러운 활동 차단
"""

import json
import time
from typing import Dict, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.status import HTTP_403_FORBIDDEN, HTTP_429_TOO_MANY_REQUESTS

from app.security.vulnerability_scanner import vulnerability_scanner, SecurityThreat
from app.security.audit_logger import audit_logger, AuditEventType, AuditSeverity

class SecurityAuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.blocked_ips = set()
        self.rate_limits = {}  # IP별 요청 제한
        
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        user_agent = request.headers.get('user-agent', '')
        
        # 차단된 IP 확인
        if client_ip in self.blocked_ips:
            await self._log_blocked_request(client_ip, "Blocked IP attempted access")
            return JSONResponse(
                content={"detail": "Access denied"}, 
                status_code=HTTP_403_FORBIDDEN
            )
        
        # Request Body 읽기 (보안 스캔용)
        body = b""
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            # Request를 다시 사용할 수 있도록 새로 생성
            from starlette.datastructures import Headers
            scope = request.scope.copy()
            scope["body"] = body
            request = Request(scope)
        
        # 보안 스캔 실행
        threats = vulnerability_scanner.scan_request(request, body.decode('utf-8', errors='ignore'))
        
        # 위협 발견 시 처리
        if threats:
            high_threats = [t for t in threats if t.get('severity') == SecurityThreat.HIGH]
            if high_threats:
                await self._handle_security_threats(client_ip, user_agent, high_threats, request)
                return JSONResponse(
                    content={"detail": "Security threat detected"}, 
                    status_code=HTTP_403_FORBIDDEN
                )
            
            # 중간 위협은 로그만 남기고 통과
            await self._log_security_threats(client_ip, user_agent, threats, request)
        
        # 요청 처리
        start_time = time.time()
        try:
            response = await call_next(request)
            
            # 응답 후 감사 로깅
            await self._log_api_access(request, response, time.time() - start_time)
            
            return response
            
        except Exception as e:
            # 에러 발생 시 감사 로깅
            await self._log_api_error(request, str(e))
            raise
    
    async def _handle_security_threats(self, ip: str, user_agent: str, 
                                       threats: List[Dict], request: Request):
        """보안 위협 처리"""
        
        # 심각한 위협 유형별 처리
        threat_types = {t.get('type') for t in threats}
        
        if SecurityThreat.SQL_INJECTION in threat_types:
            # SQL 인젝션 시도 - IP 즉시 차단
            self.blocked_ips.add(ip)
            vulnerability_scanner.add_suspicious_ip(ip, "SQL Injection Attempt")
            
            audit_logger.log_security_threat(
                threat_type="sql_injection_blocked",
                user_ip=ip,
                details={
                    "user_agent": user_agent,
                    "endpoint": str(request.url),
                    "threats": threats,
                    "action_taken": "ip_blocked"
                }
            )
        
        elif SecurityThreat.XSS in threat_types:
            # XSS 시도 - 경고 및 기록
            vulnerability_scanner.add_suspicious_ip(ip, "XSS Attempt")
            
            audit_logger.log_security_threat(
                threat_type="xss_attempt",
                user_ip=ip,
                details={
                    "user_agent": user_agent,
                    "endpoint": str(request.url),
                    "threats": threats
                }
            )
        
        elif SecurityThreat.AUTH_BYPASS in threat_types:
            # 인증 우회 시도 - 실패 기록
            vulnerability_scanner.record_failed_attempt(ip, str(request.url))
            
            audit_logger.log_security_threat(
                threat_type="auth_bypass_attempt", 
                user_ip=ip,
                details={
                    "user_agent": user_agent,
                    "endpoint": str(request.url),
                    "threats": threats
                }
            )
    
    async def _log_security_threats(self, ip: str, user_agent: str, 
                                    threats: List[Dict], request: Request):
        """보안 위협 로깅 (차단하지 않는 경우)"""
        for threat in threats:
            audit_logger.log_event(
                event_type=AuditEventType.SECURITY_THREAT,
                severity=AuditSeverity.WARNING,
                user_ip=ip,
                user_agent=user_agent,
                endpoint=str(request.url),
                http_method=request.method,
                action="threat_detected",
                details={
                    "threat_type": threat.get('type'),
                    "threat_severity": threat.get('severity'),
                    "threat_details": threat
                }
            )
    
    async def _log_api_access(self, request: Request, response: Response, 
                              duration: float):
        """API 접근 로깅"""
        
        # 인증된 사용자 정보 추출 (가능한 경우)
        user_info = await self._extract_user_info(request)
        
        audit_logger.log_event(
            event_type=AuditEventType.API_ACCESS,
            severity=AuditSeverity.INFO,
            user_id=user_info.get('user_id'),
            user_email=user_info.get('user_email'), 
            user_role=user_info.get('user_role'),
            user_ip=request.client.host,
            user_agent=request.headers.get('user-agent'),
            endpoint=str(request.url),
            http_method=request.method,
            response_status=response.status_code,
            details={
                'response_time': round(duration, 3),
                'content_type': response.headers.get('content-type'),
                'user_authenticated': user_info.get('authenticated', False)
            }
        )
    
    async def _log_api_error(self, request: Request, error: str):
        """API 에러 로깅"""
        user_info = await self._extract_user_info(request)
        
        audit_logger.log_event(
            event_type=AuditEventType.API_ACCESS,
            severity=AuditSeverity.ERROR,
            user_id=user_info.get('user_id'),
            user_email=user_info.get('user_email'),
            user_ip=request.client.host,
            endpoint=str(request.url),
            http_method=request.method,
            response_status=500,
            details={
                'error': error,
                'user_authenticated': user_info.get('authenticated', False)
            }
        )
    
    async def _log_blocked_request(self, ip: str, reason: str):
        """차단된 요청 로깅"""
        audit_logger.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.ERROR,
            user_ip=ip,
            action="request_blocked",
            details={'reason': reason}
        )
    
    async def _extract_user_info(self, request: Request) -> Dict:
        """요청에서 사용자 정보 추출"""
        user_info = {
            'user_id': None,
            'user_email': None, 
            'user_role': None,
            'authenticated': False
        }
        
        # Authorization 헤더에서 토큰 추출 시도
        auth_header = request.headers.get('authorization')
        if auth_header and auth_header.startswith('Bearer '):
            try:
                # JWT 토큰 파싱 (실제 구현에서는 jwt 라이브러리 사용)
                # 여기서는 간단히 쿼리 파라미터에서 사용자 정보 추출
                if 'viewerId' in request.query_params:
                    user_info.update({
                        'user_id': request.query_params.get('viewerId'),
                        'user_role': request.query_params.get('viewerRole'),
                        'authenticated': True
                    })
                elif 'adminId' in request.query_params:
                    user_info.update({
                        'user_id': request.query_params.get('adminId'),
                        'user_role': request.query_params.get('adminRole'),
                        'authenticated': True
                    })
            except:
                pass
        
        return user_info