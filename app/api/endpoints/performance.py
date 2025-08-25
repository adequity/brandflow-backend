"""
Performance monitoring API endpoints
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any

router = APIRouter()

# 성능 통계 조회 함수
def get_performance_statistics() -> Dict[str, Any]:
    """성능 통계 조회"""
    from app.middleware.simple_performance import get_performance_stats
    return get_performance_stats()


@router.get("/stats")
async def api_get_performance_stats():
    """
    성능 통계 조회
    - 전체 요청 수, 평균 응답 시간
    - 엔드포인트별 상세 통계
    - 느린 요청 목록
    """
    return get_performance_statistics()


@router.get("/stats/summary") 
async def get_performance_summary():
    """성능 요약 정보"""
    stats = get_performance_statistics()
    
    # 가장 느린 엔드포인트 찾기
    slowest_endpoint = None
    slowest_time = 0
    
    for endpoint, data in stats.get("endpoints", {}).items():
        avg_time = data.get("avg_time", 0)
        if avg_time > slowest_time:
            slowest_time = avg_time
            slowest_endpoint = endpoint
    
    # 가장 많이 호출된 엔드포인트
    most_called_endpoint = None
    most_calls = 0
    
    for endpoint, data in stats.get("endpoints", {}).items():
        count = data.get("count", 0)
        if count > most_calls:
            most_calls = count
            most_called_endpoint = endpoint
    
    return {
        "total_requests": stats.get("total_requests", 0),
        "avg_response_time_ms": round(stats.get("avg_response_time", 0), 1),
        "slowest_endpoint": {
            "endpoint": slowest_endpoint,
            "avg_time_ms": round(slowest_time, 1)
        },
        "most_called_endpoint": {
            "endpoint": most_called_endpoint,
            "call_count": most_calls
        },
        "slow_requests_count": len(stats.get("slow_requests", [])),
        "total_endpoints": len(stats.get("endpoints", {}))
    }


@router.get("/stats/slow-requests")
async def get_slow_requests():
    """느린 요청 목록 (500ms 이상)"""
    stats = get_performance_statistics()
        
    return {
        "slow_requests": stats.get("slow_requests", []),
        "threshold_ms": 500,
        "description": "Requests that took longer than 500ms"
    }


@router.post("/stats/reset")
async def reset_performance_statistics():
    """성능 통계 초기화"""
    from app.middleware.simple_performance import reset_performance_stats
    reset_performance_stats()
    return {"message": "Performance statistics reset successfully"}


@router.get("/health")
async def performance_health_check():
    """성능 기반 헬스 체크"""
    stats = get_performance_statistics()
    
    avg_time = stats.get("avg_response_time", 0)
    slow_requests = len(stats.get("slow_requests", []))
    
    # 헬스 상태 결정
    if avg_time > 1000:  # 평균 1초 이상
        status = "unhealthy"
        message = f"Average response time too high: {avg_time:.1f}ms"
    elif slow_requests > 5:  # 느린 요청이 5개 이상
        status = "degraded" 
        message = f"Too many slow requests: {slow_requests}"
    elif avg_time > 500:  # 평균 500ms 이상
        status = "degraded"
        message = f"Response time elevated: {avg_time:.1f}ms"
    else:
        status = "healthy"
        message = "All performance metrics within acceptable range"
    
    return {
        "status": status,
        "message": message,
        "metrics": {
            "avg_response_time_ms": round(avg_time, 1),
            "slow_requests_count": slow_requests,
            "total_requests": stats.get("total_requests", 0)
        }
    }