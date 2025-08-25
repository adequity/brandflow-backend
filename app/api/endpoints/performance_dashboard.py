"""
성능 모니터링 대시보드 API
- 실시간 성능 메트릭 조회
- 느린 쿼리 및 엔드포인트 분석
- 시스템 리소스 사용량
- 성능 알림 및 경고
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Optional
import psutil
import asyncio
from datetime import datetime, timedelta

from app.middleware.performance_monitor import performance_monitor
from app.api.deps import get_current_active_user
from app.models.user import User

router = APIRouter()

@router.get("/metrics/summary", response_model=Dict)
async def get_performance_summary():
    """전체 성능 요약"""
    return performance_monitor.get_summary()

@router.get("/metrics/endpoints", response_model=Dict)
async def get_endpoint_performance(
    slow_only: bool = Query(False, description="느린 엔드포인트만 조회")
):
    """엔드포인트별 성능 통계"""
    endpoint_stats = {}
    
    for endpoint in performance_monitor.metrics['response_times'].keys():
        stats = performance_monitor.get_endpoint_stats(endpoint)
        if slow_only and stats['avg'] < 0.1:  # 100ms 미만 제외
            continue
        endpoint_stats[endpoint] = stats
    
    # 평균 응답시간 기준 정렬
    sorted_endpoints = sorted(
        endpoint_stats.items(), 
        key=lambda x: x[1]['avg'], 
        reverse=True
    )
    
    return {
        'endpoints': dict(sorted_endpoints[:20]),  # 상위 20개
        'total_endpoints': len(endpoint_stats)
    }

@router.get("/metrics/slow-queries", response_model=List[Dict])
async def get_slow_queries(
    limit: int = Query(50, ge=1, le=100)
):
    """느린 쿼리 목록"""
    queries = list(performance_monitor.metrics['slow_queries'])
    return queries[-limit:]  # 최근 쿼리들

@router.get("/metrics/system", response_model=Dict)
async def get_system_metrics():
    """시스템 리소스 사용량"""
    # CPU 사용률
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # 메모리 사용률
    memory = psutil.virtual_memory()
    
    # 디스크 사용률
    disk = psutil.disk_usage('/')
    
    # 네트워크 I/O
    network = psutil.net_io_counters()
    
    return {
        'cpu': {
            'percent': cpu_percent,
            'count': psutil.cpu_count(),
        },
        'memory': {
            'total': round(memory.total / 1024 / 1024 / 1024, 2),  # GB
            'available': round(memory.available / 1024 / 1024 / 1024, 2),
            'percent': memory.percent,
            'used': round(memory.used / 1024 / 1024 / 1024, 2),
        },
        'disk': {
            'total': round(disk.total / 1024 / 1024 / 1024, 2),  # GB
            'used': round(disk.used / 1024 / 1024 / 1024, 2),
            'free': round(disk.free / 1024 / 1024 / 1024, 2),
            'percent': round(disk.used / disk.total * 100, 1),
        },
        'network': {
            'bytes_sent': network.bytes_sent,
            'bytes_recv': network.bytes_recv,
            'packets_sent': network.packets_sent,
            'packets_recv': network.packets_recv,
        },
        'timestamp': datetime.now().isoformat()
    }

@router.get("/metrics/realtime", response_model=Dict)
async def get_realtime_metrics():
    """실시간 성능 메트릭"""
    summary = performance_monitor.get_summary()
    system = await get_system_metrics()
    
    # 최근 10분간 요청 패턴
    recent_requests = []
    for endpoint, times in performance_monitor.metrics['response_times'].items():
        if times:
            recent_avg = sum(list(times)[-10:]) / min(len(times), 10)
            recent_requests.append({
                'endpoint': endpoint,
                'recent_avg': round(recent_avg, 3),
                'count': len(times)
            })
    
    # 성능 등급 계산
    overall_health = "healthy"
    if summary.get('slow_queries_count', 0) > 10:
        overall_health = "warning"
    if any(ep.get('avg_time', 0) > 2.0 for ep in summary.get('slow_endpoints', [])):
        overall_health = "critical"
    
    return {
        'health_status': overall_health,
        'performance_summary': summary,
        'system_metrics': system,
        'recent_requests': sorted(recent_requests, key=lambda x: x['recent_avg'], reverse=True)[:10],
        'alerts': _generate_performance_alerts(summary, system)
    }

@router.post("/metrics/reset")
async def reset_metrics(
    current_user: User = Depends(get_current_active_user)
):
    """성능 메트릭 초기화 (관리자만)"""
    if current_user.role not in ['슈퍼 어드민', 'SUPER_ADMIN']:
        raise HTTPException(status_code=403, detail="관리자만 메트릭을 초기화할 수 있습니다")
    
    # 메트릭 초기화
    performance_monitor.metrics = {
        'requests_total': 0,
        'requests_per_endpoint': {},
        'response_times': {},
        'slow_queries': [],
        'error_count': {},
        'memory_usage': [],
        'active_connections': 0,
    }
    
    return {"message": "성능 메트릭이 초기화되었습니다", "reset_at": datetime.now().isoformat()}

def _generate_performance_alerts(summary: Dict, system: Dict) -> List[Dict]:
    """성능 알림 생성"""
    alerts = []
    
    # 느린 엔드포인트 알림
    for endpoint in summary.get('slow_endpoints', []):
        if endpoint.get('avg_time', 0) > 1.0:
            alerts.append({
                'type': 'warning',
                'category': 'api_performance',
                'message': f"엔드포인트 {endpoint['endpoint']}의 평균 응답시간이 {endpoint['avg_time']}초입니다",
                'severity': 'high' if endpoint['avg_time'] > 2.0 else 'medium'
            })
    
    # 메모리 사용량 알림
    memory_percent = system.get('memory', {}).get('percent', 0)
    if memory_percent > 80:
        alerts.append({
            'type': 'warning',
            'category': 'system_resources',
            'message': f"메모리 사용량이 {memory_percent}%입니다",
            'severity': 'high' if memory_percent > 90 else 'medium'
        })
    
    # CPU 사용량 알림
    cpu_percent = system.get('cpu', {}).get('percent', 0)
    if cpu_percent > 80:
        alerts.append({
            'type': 'warning',
            'category': 'system_resources',
            'message': f"CPU 사용량이 {cpu_percent}%입니다",
            'severity': 'high' if cpu_percent > 90 else 'medium'
        })
    
    # 느린 쿼리 알림
    slow_queries_count = summary.get('slow_queries_count', 0)
    if slow_queries_count > 20:
        alerts.append({
            'type': 'warning',
            'category': 'database_performance',
            'message': f"최근 {slow_queries_count}개의 느린 쿼리가 감지되었습니다",
            'severity': 'medium'
        })
    
    return alerts

@router.get("/health/detailed", response_model=Dict)
async def detailed_health_check():
    """상세 헬스 체크"""
    try:
        # 데이터베이스 연결 테스트
        from app.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # API 응답성 테스트
    summary = performance_monitor.get_summary()
    avg_response_time = 0
    if summary.get('slow_endpoints'):
        avg_response_time = sum(ep.get('avg_time', 0) for ep in summary['slow_endpoints']) / len(summary['slow_endpoints'])
    
    api_status = "healthy"
    if avg_response_time > 2.0:
        api_status = "degraded"
    elif avg_response_time > 5.0:
        api_status = "unhealthy"
    
    # 전체 상태 결정
    overall_status = "healthy"
    if db_status != "healthy" or api_status != "healthy":
        overall_status = "unhealthy"
    elif api_status == "degraded":
        overall_status = "degraded"
    
    return {
        'status': overall_status,
        'timestamp': datetime.now().isoformat(),
        'components': {
            'database': db_status,
            'api': api_status,
            'system': 'healthy'
        },
        'metrics': {
            'avg_response_time': round(avg_response_time, 3),
            'total_requests': summary.get('total_requests', 0),
            'active_connections': summary.get('active_connections', 0)
        }
    }