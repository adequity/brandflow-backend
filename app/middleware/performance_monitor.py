"""
고급 성능 모니터링 미들웨어
- API 응답 시간 추적
- 메모리 사용량 모니터링  
- 느린 쿼리 감지
- 실시간 성능 메트릭
"""

import time
import asyncio
import psutil
import json
from datetime import datetime
from typing import Dict, List
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy import event
from sqlalchemy.engine import Engine

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'requests_total': 0,
            'requests_per_endpoint': defaultdict(int),
            'response_times': defaultdict(deque),
            'slow_queries': deque(maxlen=100),
            'error_count': defaultdict(int),
            'memory_usage': deque(maxlen=100),
            'active_connections': 0,
        }
        
        # 최근 100개 요청의 응답시간만 보관
        for endpoint_times in self.metrics['response_times'].values():
            endpoint_times = deque(maxlen=100)
    
    def record_request(self, endpoint: str, method: str, duration: float, status_code: int):
        """API 요청 성능 기록"""
        self.metrics['requests_total'] += 1
        self.metrics['requests_per_endpoint'][f"{method} {endpoint}"] += 1
        self.metrics['response_times'][endpoint].append(duration)
        
        if status_code >= 400:
            self.metrics['error_count'][status_code] += 1
    
    def record_memory_usage(self):
        """메모리 사용량 기록"""
        memory_info = psutil.Process().memory_info()
        self.metrics['memory_usage'].append({
            'timestamp': datetime.now().isoformat(),
            'rss': memory_info.rss / 1024 / 1024,  # MB
            'vms': memory_info.vms / 1024 / 1024,   # MB
        })
    
    def get_endpoint_stats(self, endpoint: str) -> Dict:
        """특정 엔드포인트 통계"""
        times = list(self.metrics['response_times'][endpoint])
        if not times:
            return {'count': 0, 'avg': 0, 'min': 0, 'max': 0}
            
        return {
            'count': len(times),
            'avg': sum(times) / len(times),
            'min': min(times),
            'max': max(times),
            'p95': sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times)
        }
    
    def get_summary(self) -> Dict:
        """성능 요약 통계"""
        self.record_memory_usage()
        
        # 가장 느린 엔드포인트들
        slow_endpoints = []
        for endpoint, times in self.metrics['response_times'].items():
            if times:
                avg_time = sum(times) / len(times)
                if avg_time > 0.1:  # 100ms 이상
                    slow_endpoints.append({
                        'endpoint': endpoint,
                        'avg_time': round(avg_time, 3),
                        'count': len(times)
                    })
        
        slow_endpoints.sort(key=lambda x: x['avg_time'], reverse=True)
        
        return {
            'total_requests': self.metrics['requests_total'],
            'active_connections': self.metrics['active_connections'],
            'slow_endpoints': slow_endpoints[:5],
            'error_rates': dict(self.metrics['error_count']),
            'memory_mb': list(self.metrics['memory_usage'])[-1] if self.metrics['memory_usage'] else None,
            'slow_queries_count': len(self.metrics['slow_queries'])
        }

# 전역 모니터 인스턴스
performance_monitor = PerformanceMonitor()

class PerformanceMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, monitor: PerformanceMonitor):
        super().__init__(app)
        self.monitor = monitor
    
    async def dispatch(self, request: Request, call_next):
        # 요청 시작 시간
        start_time = time.time()
        self.monitor.metrics['active_connections'] += 1
        
        try:
            # 요청 처리
            response = await call_next(request)
            
            # 성능 메트릭 기록
            duration = time.time() - start_time
            endpoint = request.url.path
            method = request.method
            status_code = response.status_code
            
            self.monitor.record_request(endpoint, method, duration, status_code)
            
            # 응답 헤더에 성능 정보 추가
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            response.headers["X-Process-Memory"] = f"{psutil.Process().memory_info().rss / 1024 / 1024:.1f}MB"
            
            # 느린 요청 경고
            if duration > 1.0:  # 1초 이상
                print(f" 느린 요청 감지: {method} {endpoint} - {duration:.3f}s")
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            self.monitor.record_request(request.url.path, request.method, duration, 500)
            raise e
            
        finally:
            self.monitor.metrics['active_connections'] -= 1

# SQLAlchemy 쿼리 모니터링
@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute") 
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - context._query_start_time
    
    # 느린 쿼리 기록 (100ms 이상)
    if total > 0.1:
        performance_monitor.metrics['slow_queries'].append({
            'query': statement[:200] + '...' if len(statement) > 200 else statement,
            'duration': round(total, 3),
            'timestamp': datetime.now().isoformat(),
            'parameters': str(parameters)[:100] if parameters else None
        })
        print(f" 느린 쿼리: {total:.3f}s - {statement[:100]}...")