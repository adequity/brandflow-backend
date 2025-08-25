"""
보안 대시보드 API
- 보안 위협 모니터링
- 감사 로그 조회
- 사용자 활동 분석  
- 규정 준수 리포트
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from app.security.vulnerability_scanner import vulnerability_scanner
from app.security.audit_logger import audit_logger, AuditEventType, AuditSeverity
from app.api.deps import get_current_active_user
from app.models.user import User

router = APIRouter()

@router.get("/security/overview", response_model=Dict)
async def get_security_overview():
    """보안 현황 개요"""
    security_report = vulnerability_scanner.generate_security_report()
    audit_summary = audit_logger.event_counts
    
    return {
        "security_threats": security_report,
        "audit_summary": audit_summary,
        "system_status": "operational",
        "last_updated": datetime.now().isoformat()
    }

@router.get("/security/threats", response_model=Dict)
async def get_security_threats(
    severity: Optional[str] = Query(None, description="위협 심각도 필터"),
    limit: int = Query(50, ge=1, le=200, description="조회할 위협 수")
):
    """보안 위협 목록"""
    report = vulnerability_scanner.generate_security_report()
    
    threats = report.get('recent_threats', [])
    if severity:
        threats = [t for t in threats if t.get('severity') == severity]
    
    return {
        "threats": threats[:limit],
        "total_count": len(threats),
        "threat_summary": report.get('threat_breakdown', {}),
        "severity_breakdown": report.get('severity_breakdown', {}),
        "suspicious_ips": report.get('top_suspicious_ips', [])
    }

@router.get("/audit/events", response_model=List[Dict])
async def get_audit_events(
    event_type: Optional[str] = Query(None, description="이벤트 유형"),
    user_email: Optional[str] = Query(None, description="사용자 이메일"),
    severity: Optional[str] = Query(None, description="심각도"),
    resource_type: Optional[str] = Query(None, description="리소스 유형"),
    limit: int = Query(100, ge=1, le=500, description="조회할 이벤트 수")
):
    """감사 로그 이벤트 조회"""
    
    # 문자열을 Enum으로 변환
    event_type_enum = None
    severity_enum = None
    
    if event_type:
        try:
            event_type_enum = AuditEventType(event_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid event type: {event_type}")
    
    if severity:
        try:
            severity_enum = AuditSeverity(severity)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
    
    events = audit_logger.get_events(
        event_type=event_type_enum,
        user_email=user_email,
        severity=severity_enum,
        resource_type=resource_type,
        limit=limit
    )
    
    # AuditEvent 객체를 딕셔너리로 변환
    return [
        {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "severity": event.severity.value,
            "user_id": event.user_id,
            "user_email": event.user_email,
            "user_role": event.user_role,
            "user_ip": event.user_ip,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "action": event.action,
            "details": event.details,
            "endpoint": event.endpoint,
            "http_method": event.http_method,
            "response_status": event.response_status,
            "timestamp": event.timestamp.isoformat()
        }
        for event in events
    ]

@router.get("/audit/user-activity/{user_email}", response_model=Dict)
async def get_user_activity(
    user_email: str,
    days: int = Query(7, ge=1, le=90, description="조회할 일수")
):
    """특정 사용자 활동 분석"""
    return audit_logger.get_user_activity_summary(user_email, days)

@router.get("/security/compliance-report", response_model=Dict)
async def get_compliance_report():
    """규정 준수 리포트"""
    return audit_logger.generate_compliance_report()

@router.get("/security/alerts", response_model=List[Dict])
async def get_security_alerts(
    severity: Optional[str] = Query(None, description="경고 심각도"),
    limit: int = Query(20, ge=1, le=100)
):
    """보안 경고 목록"""
    # 보안 이벤트 중 경고성 이벤트만 필터링
    severity_filter = AuditSeverity(severity) if severity else None
    
    events = audit_logger.get_events(
        event_type=AuditEventType.SECURITY_THREAT,
        severity=severity_filter,
        limit=limit
    )
    
    alerts = []
    for event in events:
        alerts.append({
            "alert_id": event.event_id,
            "type": event.action,
            "severity": event.severity.value,
            "user_ip": event.user_ip,
            "message": f"Security threat detected: {event.action}",
            "details": event.details,
            "timestamp": event.timestamp.isoformat(),
            "resolved": False  # 실제로는 상태 관리 필요
        })
    
    return alerts

@router.get("/audit/statistics", response_model=Dict)
async def get_audit_statistics(
    days: int = Query(30, ge=1, le=365, description="통계 기간(일)")
):
    """감사 통계"""
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # 기간 내 이벤트 필터링
    events = [
        e for e in audit_logger.events 
        if e.timestamp >= cutoff_date
    ]
    
    # 통계 계산
    stats = {
        'period_days': days,
        'total_events': len(events),
        'events_by_type': {},
        'events_by_severity': {},
        'events_by_day': {},
        'active_users': set(),
        'top_endpoints': {},
        'security_incidents': 0
    }
    
    for event in events:
        # 타입별 집계
        event_type = event.event_type.value
        stats['events_by_type'][event_type] = stats['events_by_type'].get(event_type, 0) + 1
        
        # 심각도별 집계
        severity = event.severity.value
        stats['events_by_severity'][severity] = stats['events_by_severity'].get(severity, 0) + 1
        
        # 일별 집계
        day = event.timestamp.date().isoformat()
        stats['events_by_day'][day] = stats['events_by_day'].get(day, 0) + 1
        
        # 활성 사용자
        if event.user_email:
            stats['active_users'].add(event.user_email)
        
        # 엔드포인트별 집계
        if event.endpoint:
            stats['top_endpoints'][event.endpoint] = stats['top_endpoints'].get(event.endpoint, 0) + 1
        
        # 보안 사고 카운트
        if event.event_type in [AuditEventType.SECURITY_THREAT, AuditEventType.SECURITY_VIOLATION]:
            stats['security_incidents'] += 1
    
    # 집합을 개수로 변환
    stats['active_users'] = len(stats['active_users'])
    
    # 상위 엔드포인트만 반환 (상위 10개)
    top_endpoints = sorted(stats['top_endpoints'].items(), key=lambda x: x[1], reverse=True)[:10]
    stats['top_endpoints'] = dict(top_endpoints)
    
    return stats

@router.post("/security/threats/resolve/{threat_id}")
async def resolve_security_threat(
    threat_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """보안 위협 해결 처리"""
    
    # 관리자 권한 확인
    if current_user.role not in ['슈퍼 어드민', 'SUPER_ADMIN']:
        raise HTTPException(status_code=403, detail="관리자만 보안 위협을 해결할 수 있습니다")
    
    # 실제로는 위협 ID를 찾아서 해결 상태로 변경
    # 여기서는 감사 로그만 기록
    audit_logger.log_admin_action(
        admin_id=current_user.id,
        admin_email=current_user.email,
        admin_ip="system",  # 실제로는 request에서 추출
        action="resolve_security_threat",
        target_resource=f"security_threat:{threat_id}"
    )
    
    return {
        "message": f"보안 위협 {threat_id}이 해결되었습니다",
        "resolved_by": current_user.email,
        "resolved_at": datetime.now().isoformat()
    }

@router.get("/security/ip-blocklist", response_model=List[str])
async def get_blocked_ips():
    """차단된 IP 목록"""
    return list(vulnerability_scanner.suspicious_ips)

@router.post("/security/ip-blocklist/{ip}")
async def block_ip(
    ip: str,
    reason: Optional[str] = Query("Manual block", description="차단 사유"),
    current_user: User = Depends(get_current_active_user)
):
    """IP 수동 차단"""
    
    # 관리자 권한 확인
    if current_user.role not in ['슈퍼 어드민', 'SUPER_ADMIN']:
        raise HTTPException(status_code=403, detail="관리자만 IP를 차단할 수 있습니다")
    
    vulnerability_scanner.add_suspicious_ip(ip, reason)
    
    audit_logger.log_admin_action(
        admin_id=current_user.id,
        admin_email=current_user.email,
        admin_ip="system",
        action="block_ip",
        target_resource=f"ip:{ip}",
        details={"reason": reason}
    )
    
    return {
        "message": f"IP {ip}이 차단되었습니다",
        "reason": reason,
        "blocked_by": current_user.email
    }

@router.delete("/security/ip-blocklist/{ip}")
async def unblock_ip(
    ip: str,
    current_user: User = Depends(get_current_active_user)
):
    """IP 차단 해제"""
    
    # 관리자 권한 확인
    if current_user.role not in ['슈퍼 어드민', 'SUPER_ADMIN']:
        raise HTTPException(status_code=403, detail="관리자만 IP 차단을 해제할 수 있습니다")
    
    if ip in vulnerability_scanner.suspicious_ips:
        vulnerability_scanner.suspicious_ips.remove(ip)
        
        audit_logger.log_admin_action(
            admin_id=current_user.id,
            admin_email=current_user.email,
            admin_ip="system",
            action="unblock_ip",
            target_resource=f"ip:{ip}"
        )
        
        return {"message": f"IP {ip} 차단이 해제되었습니다"}
    else:
        raise HTTPException(status_code=404, detail="차단되지 않은 IP입니다")