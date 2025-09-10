"""
감사 로그 시스템
- 사용자 활동 추적
- 권한 변경 기록
- 데이터 접근 로깅
- 보안 이벤트 기록
- 규정 준수 리포트
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
from collections import deque
import hashlib

class AuditEventType(str, Enum):
    """감사 이벤트 유형"""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout" 
    USER_LOGIN_FAILED = "user_login_failed"
    
    DATA_CREATE = "data_create"
    DATA_READ = "data_read"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"
    
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    ROLE_CHANGED = "role_changed"
    
    SECURITY_THREAT = "security_threat"
    SECURITY_VIOLATION = "security_violation"
    
    API_ACCESS = "api_access"
    FILE_DOWNLOAD = "file_download"
    FILE_UPLOAD = "file_upload"
    
    SYSTEM_CONFIG = "system_config"
    ADMIN_ACTION = "admin_action"

class AuditSeverity(str, Enum):
    """감사 로그 심각도"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class AuditEvent:
    """감사 이벤트 데이터 구조"""
    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    user_ip: Optional[str] = None
    user_agent: Optional[str] = None
    
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    
    action: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    endpoint: Optional[str] = None
    http_method: Optional[str] = None
    response_status: Optional[int] = None
    
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.event_id is None:
            self.event_id = str(uuid.uuid4())

class AuditLogger:
    def __init__(self, max_events: int = 10000):
        self.events = deque(maxlen=max_events)
        self.event_counts = {
            'total': 0,
            'by_type': {},
            'by_severity': {},
            'by_user': {},
            'today': 0
        }
    
    def log_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        user_role: Optional[str] = None,
        user_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        http_method: Optional[str] = None,
        response_status: Optional[int] = None
    ) -> AuditEvent:
        """감사 이벤트 기록"""
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            user_ip=user_ip,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            action=action,
            details=details,
            old_values=old_values,
            new_values=new_values,
            request_id=request_id,
            session_id=session_id,
            endpoint=endpoint,
            http_method=http_method,
            response_status=response_status
        )
        
        self.events.append(event)
        self._update_counts(event)
        
        # 중요 이벤트는 즉시 출력
        if severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]:
            self._print_critical_event(event)
        
        return event
    
    def _update_counts(self, event: AuditEvent):
        """이벤트 통계 업데이트"""
        self.event_counts['total'] += 1
        
        # 타입별 카운트
        event_type = event.event_type.value
        self.event_counts['by_type'][event_type] = \
            self.event_counts['by_type'].get(event_type, 0) + 1
        
        # 심각도별 카운트
        severity = event.severity.value
        self.event_counts['by_severity'][severity] = \
            self.event_counts['by_severity'].get(severity, 0) + 1
        
        # 사용자별 카운트
        if event.user_email:
            self.event_counts['by_user'][event.user_email] = \
                self.event_counts['by_user'].get(event.user_email, 0) + 1
        
        # 오늘 카운트
        if event.timestamp.date() == datetime.now().date():
            self.event_counts['today'] += 1
    
    def _print_critical_event(self, event: AuditEvent):
        """중요 이벤트 즉시 출력"""
        print(f" CRITICAL AUDIT EVENT: {event.event_type.value}")
        print(f"   User: {event.user_email} ({event.user_role})")
        print(f"   IP: {event.user_ip}")
        print(f"   Action: {event.action}")
        print(f"   Details: {event.details}")
        print(f"   Time: {event.timestamp}")
    
    # 특화된 로깅 메서드들
    def log_login_success(self, user_id: int, user_email: str, user_role: str, 
                          user_ip: str, user_agent: str):
        """로그인 성공 기록"""
        return self.log_event(
            event_type=AuditEventType.USER_LOGIN,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            user_ip=user_ip,
            user_agent=user_agent,
            action="login_success",
            details={"login_method": "password"}
        )
    
    def log_login_failed(self, email: str, user_ip: str, reason: str):
        """로그인 실패 기록"""
        return self.log_event(
            event_type=AuditEventType.USER_LOGIN_FAILED,
            severity=AuditSeverity.WARNING,
            user_email=email,
            user_ip=user_ip,
            action="login_failed",
            details={"reason": reason, "login_method": "password"}
        )
    
    def log_data_access(self, user_id: int, user_email: str, user_role: str,
                        resource_type: str, resource_id: str, action: str,
                        user_ip: str = None, details: Dict = None):
        """데이터 접근 기록"""
        return self.log_event(
            event_type=AuditEventType.DATA_READ if action == "read" else AuditEventType.DATA_UPDATE,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            user_ip=user_ip,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details
        )
    
    def log_permission_denied(self, user_id: int, user_email: str, user_role: str,
                              resource_type: str, action: str, user_ip: str,
                              reason: str = None):
        """권한 거부 기록"""
        return self.log_event(
            event_type=AuditEventType.PERMISSION_DENIED,
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            user_ip=user_ip,
            resource_type=resource_type,
            action=action,
            details={"reason": reason}
        )
    
    def log_security_threat(self, threat_type: str, user_ip: str, details: Dict):
        """보안 위협 기록"""
        return self.log_event(
            event_type=AuditEventType.SECURITY_THREAT,
            severity=AuditSeverity.ERROR,
            user_ip=user_ip,
            action=threat_type,
            details=details
        )
    
    def log_admin_action(self, admin_id: int, admin_email: str, admin_ip: str,
                         action: str, target_resource: str, old_values: Dict = None,
                         new_values: Dict = None):
        """관리자 작업 기록"""
        return self.log_event(
            event_type=AuditEventType.ADMIN_ACTION,
            severity=AuditSeverity.INFO,
            user_id=admin_id,
            user_email=admin_email,
            user_ip=admin_ip,
            action=action,
            resource_type=target_resource,
            old_values=old_values,
            new_values=new_values
        )
    
    # 조회 메서드들
    def get_events(self, 
                   event_type: Optional[AuditEventType] = None,
                   user_email: Optional[str] = None,
                   severity: Optional[AuditSeverity] = None,
                   resource_type: Optional[str] = None,
                   limit: int = 100) -> List[AuditEvent]:
        """감사 이벤트 조회"""
        
        events = list(self.events)
        
        # 필터링
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if user_email:
            events = [e for e in events if e.user_email == user_email]
        if severity:
            events = [e for e in events if e.severity == severity]
        if resource_type:
            events = [e for e in events if e.resource_type == resource_type]
        
        # 최신순 정렬 후 제한
        events.sort(key=lambda x: x.timestamp, reverse=True)
        return events[:limit]
    
    def get_user_activity_summary(self, user_email: str, days: int = 7) -> Dict:
        """사용자 활동 요약"""
        cutoff_date = datetime.now().date() - timedelta(days=days)
        user_events = [
            e for e in self.events 
            if e.user_email == user_email and e.timestamp.date() >= cutoff_date
        ]
        
        activity_by_day = {}
        event_types = {}
        resources_accessed = set()
        
        for event in user_events:
            day = event.timestamp.date().isoformat()
            activity_by_day[day] = activity_by_day.get(day, 0) + 1
            
            event_type = event.event_type.value
            event_types[event_type] = event_types.get(event_type, 0) + 1
            
            if event.resource_type:
                resources_accessed.add(f"{event.resource_type}:{event.resource_id}")
        
        return {
            'user_email': user_email,
            'period_days': days,
            'total_events': len(user_events),
            'activity_by_day': activity_by_day,
            'event_types': event_types,
            'unique_resources': len(resources_accessed),
            'last_activity': user_events[0].timestamp.isoformat() if user_events else None
        }
    
    def generate_compliance_report(self) -> Dict:
        """규정 준수 리포트"""
        total_events = len(self.events)
        if total_events == 0:
            return {'message': 'No events to report'}
        
        # 최근 30일 이벤트
        recent_date = datetime.now().date() - timedelta(days=30)
        recent_events = [
            e for e in self.events 
            if e.timestamp.date() >= recent_date
        ]
        
        # 보안 이벤트 분석
        security_events = [
            e for e in recent_events 
            if e.event_type in [AuditEventType.SECURITY_THREAT, AuditEventType.PERMISSION_DENIED, AuditEventType.USER_LOGIN_FAILED]
        ]
        
        # 데이터 접근 분석
        data_access_events = [
            e for e in recent_events 
            if e.event_type in [AuditEventType.DATA_READ, AuditEventType.DATA_UPDATE, AuditEventType.DATA_DELETE]
        ]
        
        return {
            'report_period': '30 days',
            'total_events': total_events,
            'recent_events': len(recent_events),
            'security_incidents': len(security_events),
            'data_access_events': len(data_access_events),
            'unique_users': len(set(e.user_email for e in recent_events if e.user_email)),
            'event_breakdown': self.event_counts['by_type'].copy(),
            'severity_breakdown': self.event_counts['by_severity'].copy(),
            'generated_at': datetime.now().isoformat()
        }

# 전역 감사 로거 인스턴스  
audit_logger = AuditLogger()