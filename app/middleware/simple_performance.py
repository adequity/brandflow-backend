"""
Simple performance monitoring middleware for FastAPI
"""

import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# 성능 로거 설정
perf_logger = logging.getLogger("performance")
perf_logger.setLevel(logging.INFO)
if not perf_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - PERF - %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    perf_logger.addHandler(handler)

# 전역 성능 통계
performance_stats = {
    "total_requests": 0,
    "total_time": 0,
    "endpoints": {},
    "slow_requests": []
}


class SimplePerformanceMiddleware(BaseHTTPMiddleware):
    """간단한 성능 모니터링 미들웨어"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 요청 처리
        response = await call_next(request)
        
        # 성능 측정
        end_time = time.time()
        duration = end_time - start_time
        duration_ms = duration * 1000
        
        # 엔드포인트 정보
        method = request.method
        path = request.url.path
        endpoint = f"{method} {path}"
        status_code = response.status_code
        
        # 통계 업데이트
        self._update_stats(endpoint, duration, status_code, duration_ms)
        
        # 로깅
        self._log_request(endpoint, duration_ms, status_code)
        
        return response
    
    def _update_stats(self, endpoint: str, duration: float, status_code: int, duration_ms: float):
        """통계 업데이트"""
        global performance_stats
        
        performance_stats["total_requests"] += 1
        performance_stats["total_time"] += duration
        
        # 엔드포인트별 통계
        if endpoint not in performance_stats["endpoints"]:
            performance_stats["endpoints"][endpoint] = {
                "count": 0,
                "total_time": 0,
                "min_time": float('inf'),
                "max_time": 0,
                "errors": 0
            }
        
        endpoint_stats = performance_stats["endpoints"][endpoint]
        endpoint_stats["count"] += 1
        endpoint_stats["total_time"] += duration
        endpoint_stats["min_time"] = min(endpoint_stats["min_time"], duration)
        endpoint_stats["max_time"] = max(endpoint_stats["max_time"], duration)
        
        if status_code >= 400:
            endpoint_stats["errors"] += 1
        
        # 느린 요청 추적 (500ms 이상)
        if duration_ms > 500:
            performance_stats["slow_requests"].append({
                "endpoint": endpoint,
                "duration_ms": round(duration_ms, 1),
                "timestamp": time.time(),
                "status_code": status_code
            })
            # 최근 10개만 유지
            performance_stats["slow_requests"] = performance_stats["slow_requests"][-10:]
    
    def _log_request(self, endpoint: str, duration_ms: float, status_code: int):
        """요청 로깅"""
        # 로그 레벨 결정
        if duration_ms > 1000:  # 1초 이상
            perf_logger.warning(f"{endpoint} - {duration_ms:.1f}ms - {status_code} [SLOW]")
        elif duration_ms > 500:  # 500ms 이상
            perf_logger.info(f"{endpoint} - {duration_ms:.1f}ms - {status_code} [ELEVATED]")
        else:
            perf_logger.debug(f"{endpoint} - {duration_ms:.1f}ms - {status_code}")


def get_performance_stats():
    """성능 통계 반환"""
    global performance_stats
    stats = performance_stats.copy()
    
    # 평균 응답 시간 계산
    if stats["total_requests"] > 0:
        stats["avg_response_time"] = stats["total_time"] / stats["total_requests"] * 1000
    else:
        stats["avg_response_time"] = 0
    
    # 엔드포인트별 평균 시간 계산
    for endpoint, data in stats["endpoints"].items():
        if data["count"] > 0:
            data["avg_time"] = data["total_time"] / data["count"] * 1000
            data["min_time_ms"] = data["min_time"] * 1000 if data["min_time"] != float('inf') else 0
            data["max_time_ms"] = data["max_time"] * 1000
    
    return stats


def reset_performance_stats():
    """통계 초기화"""
    global performance_stats
    performance_stats = {
        "total_requests": 0,
        "total_time": 0,
        "endpoints": {},
        "slow_requests": []
    }