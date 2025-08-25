"""
Performance monitoring middleware for BrandFlow API
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import asyncio

# 성능 로거 설정
perf_logger = logging.getLogger("brandflow.performance")
perf_logger.setLevel(logging.INFO)

# 콘솔 핸들러 설정
if not perf_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - PERF - %(message)s", 
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    perf_logger.addHandler(handler)


class PerformanceMonitoringMiddleware:
    """API 성능 모니터링 미들웨어"""
    
    def __init__(self, app):
        self.app = app
        # 성능 통계 저장
        self.stats = {
            "total_requests": 0,
            "total_time": 0,
            "endpoints": {},
            "slow_requests": []  # 500ms 이상 걸린 요청들
        }
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # 시작 시간 기록
        start_time = time.time()
        
        # Request 객체 생성
        request = Request(scope, receive)
        
        # Response 캡처를 위한 래퍼
        response_body = None
        status_code = None
        
        async def send_wrapper(message):
            nonlocal response_body, status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                response_body = message.get("body", b"")
            await send(message)
        
        try:
            # 애플리케이션 실행
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            # 에러 발생 시에도 성능 측정
            end_time = time.time()
            duration = end_time - start_time
            await self._log_request(request, 500, duration, error=str(e))
            raise
        else:
            # 정상 처리 시 성능 측정
            end_time = time.time()
            duration = end_time - start_time
            await self._log_request(request, status_code or 200, duration)
    
    async def _log_request(self, request: Request, status_code: int, duration: float, error: str = None):
        """요청 성능 로깅"""
        
        # 기본 정보
        method = request.method
        path = request.url.path
        endpoint = f"{method} {path}"
        duration_ms = duration * 1000
        
        # 통계 업데이트
        self.stats["total_requests"] += 1
        self.stats["total_time"] += duration
        
        if endpoint not in self.stats["endpoints"]:
            self.stats["endpoints"][endpoint] = {
                "count": 0,
                "total_time": 0,
                "min_time": float('inf'),
                "max_time": 0,
                "errors": 0
            }
        
        endpoint_stats = self.stats["endpoints"][endpoint]
        endpoint_stats["count"] += 1
        endpoint_stats["total_time"] += duration
        endpoint_stats["min_time"] = min(endpoint_stats["min_time"], duration)
        endpoint_stats["max_time"] = max(endpoint_stats["max_time"], duration)
        
        if status_code >= 400:
            endpoint_stats["errors"] += 1
        
        # 느린 요청 추적 (500ms 이상)
        if duration_ms > 500:
            self.stats["slow_requests"].append({
                "endpoint": endpoint,
                "duration_ms": duration_ms,
                "timestamp": time.time(),
                "status_code": status_code,
                "error": error
            })
            # 최근 10개만 유지
            self.stats["slow_requests"] = self.stats["slow_requests"][-10:]
        
        # 로그 레벨 결정
        log_level = logging.INFO
        if duration_ms > 1000:  # 1초 이상
            log_level = logging.WARNING
        elif duration_ms > 2000:  # 2초 이상
            log_level = logging.ERROR
        
        # 성능 로그 출력
        log_msg = f"{endpoint} - {duration_ms:.1f}ms - {status_code}"
        if error:
            log_msg += f" - ERROR: {error}"
        
        perf_logger.log(log_level, log_msg)
        
        # 매우 느린 요청에 대한 상세 로깅
        if duration_ms > 1000:
            perf_logger.warning(f"SLOW REQUEST DETECTED: {endpoint} took {duration_ms:.1f}ms")
    
    def get_stats(self):
        """성능 통계 반환"""
        stats = self.stats.copy()
        
        # 평균 응답 시간 계산
        if stats["total_requests"] > 0:
            stats["avg_response_time"] = stats["total_time"] / stats["total_requests"] * 1000
        else:
            stats["avg_response_time"] = 0
        
        # 엔드포인트별 평균 시간 계산
        for endpoint, data in stats["endpoints"].items():
            if data["count"] > 0:
                data["avg_time"] = data["total_time"] / data["count"] * 1000
                data["min_time_ms"] = data["min_time"] * 1000
                data["max_time_ms"] = data["max_time"] * 1000
        
        return stats
    
    def reset_stats(self):
        """통계 초기화"""
        self.stats = {
            "total_requests": 0,
            "total_time": 0,
            "endpoints": {},
            "slow_requests": []
        }