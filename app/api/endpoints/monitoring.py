"""
모니터링 API 엔드포인트
시스템 상태, 헬스 체크, 로그 조회 기능
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import time

from app.middleware.monitoring import get_monitoring_instance
from app.api.deps import get_current_active_user, User

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    시스템 헬스 체크
    - 기본적인 서비스 상태 확인
    - 인증 불필요
    """
    monitoring = get_monitoring_instance()
    if not monitoring:
        return {"status": "healthy", "message": "Monitoring not initialized"}
    
    health = monitoring.system_monitor.check_health()
    
    return {
        "status": health["status"],
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": health["uptime"],
        "checks": {
            "cpu": {"status": "ok" if health["cpu"] < 80 else "warning", "value": health["cpu"]},
            "memory": {"status": "ok" if health["memory"] < 85 else "warning", "value": health["memory"]},
            "disk": {"status": "ok" if health["disk"] < 90 else "critical", "value": health["disk"]}
        },
        "warnings": health.get("warnings", [])
    }


@router.get("/system")
async def get_system_stats(current_user: User = Depends(get_current_active_user)):
    """
    시스템 리소스 통계
    - CPU, 메모리, 디스크 사용량
    - 관리자만 접근 가능
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    monitoring = get_monitoring_instance()
    if not monitoring:
        raise HTTPException(status_code=503, detail="Monitoring service not available")
    
    stats = monitoring.get_monitoring_stats()
    
    return {
        "system": stats["system"],
        "health": stats["health"],
        "uptime": stats["uptime"],
        "requests": {
            "total": stats["requests"]["total"],
            "successful": stats["requests"]["successful"],
            "failed": stats["requests"]["failed"],
            "active": stats["requests"]["active"],
            "success_rate": (stats["requests"]["successful"] / max(stats["requests"]["total"], 1)) * 100
        }
    }


@router.get("/requests")
async def get_request_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user)
):
    """
    최근 요청 로그 조회
    - HTTP 요청/응답 로그
    - 관리자만 접근 가능
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    monitoring = get_monitoring_instance()
    if not monitoring:
        raise HTTPException(status_code=503, detail="Monitoring service not available")
    
    logs = monitoring.get_request_logs(limit)
    
    return {
        "logs": logs,
        "total": len(logs),
        "limit": limit
    }


@router.get("/errors")
async def get_error_logs(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user)
):
    """
    에러 로그 조회
    - 시스템 에러 및 예외 로그
    - 관리자만 접근 가능
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    monitoring = get_monitoring_instance()
    if not monitoring:
        raise HTTPException(status_code=503, detail="Monitoring service not available")
    
    stats = monitoring.get_monitoring_stats()
    errors = stats["recent_errors"][-limit:]
    
    return {
        "errors": errors,
        "total": len(errors),
        "limit": limit
    }


@router.get("/alerts")
async def get_alerts(
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_active_user)
):
    """
    시스템 알림 조회
    - 리소스 경고 및 중요 알림
    - 관리자만 접근 가능
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    monitoring = get_monitoring_instance()
    if not monitoring:
        raise HTTPException(status_code=503, detail="Monitoring service not available")
    
    stats = monitoring.get_monitoring_stats()
    alerts = stats["alerts"][-limit:]
    
    return {
        "alerts": alerts,
        "total": len(alerts),
        "limit": limit
    }


@router.get("/dashboard")
async def get_monitoring_dashboard(current_user: User = Depends(get_current_active_user)):
    """
    모니터링 대시보드 데이터
    - 전체 시스템 상태 요약
    - 관리자만 접근 가능
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    monitoring = get_monitoring_instance()
    if not monitoring:
        raise HTTPException(status_code=503, detail="Monitoring service not available")
    
    stats = monitoring.get_monitoring_stats()
    health = stats["health"]
    
    # 성능 메트릭 계산
    total_requests = stats["requests"]["total"]
    success_rate = (stats["requests"]["successful"] / max(total_requests, 1)) * 100
    
    # 최근 요청 로그에서 평균 응답 시간 계산
    recent_logs = monitoring.get_request_logs(100)
    avg_response_time = 0
    if recent_logs:
        total_time = sum(log.get("duration", 0) for log in recent_logs)
        avg_response_time = (total_time / len(recent_logs)) * 1000  # ms로 변환
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "status": health["status"],
        "uptime": stats["uptime"],
        "system": {
            "cpu": health["cpu"],
            "memory": health["memory"],
            "disk": health["disk"]
        },
        "requests": {
            "total": total_requests,
            "success_rate": round(success_rate, 2),
            "active": stats["requests"]["active"],
            "avg_response_time": round(avg_response_time, 1)
        },
        "recent_alerts": len([a for a in stats["alerts"] if a.get("level") == "critical"]),
        "recent_errors": len(stats["recent_errors"]),
        "warnings": health.get("warnings", [])
    }


@router.post("/reset-stats")
async def reset_monitoring_stats(current_user: User = Depends(get_current_active_user)):
    """
    모니터링 통계 초기화
    - 요청 카운터 및 통계 리셋
    - 관리자만 접근 가능
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    monitoring = get_monitoring_instance()
    if not monitoring:
        raise HTTPException(status_code=503, detail="Monitoring service not available")
    
    # 통계 초기화 (시스템 상태는 유지)
    from app.middleware.monitoring import monitoring_state
    monitoring_state["requests"] = {
        "total": 0,
        "successful": 0,
        "failed": 0,
        "active": 0
    }
    monitoring_state["errors"] = []
    monitoring_state["alerts"] = []
    
    # 요청 로그 초기화
    monitoring.request_log = []
    
    return {
        "message": "모니터링 통계가 초기화되었습니다.",
        "timestamp": datetime.utcnow().isoformat()
    }