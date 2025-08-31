"""
모니터링 및 로깅 미들웨어 시스템
통합된 로깅, 헬스 체크, 시스템 모니터링 기능
"""

import time
import json
import asyncio
import logging
import psutil
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import uuid

# 시스템 모니터링 로거 설정
monitor_logger = logging.getLogger("brandflow.monitor")
monitor_logger.setLevel(logging.INFO)

if not monitor_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - MONITOR - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    monitor_logger.addHandler(handler)

# 전역 모니터링 상태
monitoring_state = {
    "requests": {
        "total": 0,
        "successful": 0,
        "failed": 0,
        "active": 0
    },
    "system": {
        "cpu_usage": 0,
        "memory_usage": 0,
        "disk_usage": 0,
        "uptime": time.time()
    },
    "errors": [],
    "health_status": "healthy",
    "alerts": []
}


class SystemMonitor:
    """시스템 리소스 모니터링"""
    
    def __init__(self):
        self.start_time = time.time()
    
    def get_cpu_usage(self) -> float:
        """CPU 사용률 (백분율)"""
        return psutil.cpu_percent(interval=0.1)
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """메모리 사용 정보"""
        memory = psutil.virtual_memory()
        return {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used
        }
    
    def get_disk_usage(self) -> Dict[str, Any]:
        """디스크 사용 정보"""
        disk = psutil.disk_usage('/')
        return {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": (disk.used / disk.total) * 100
        }
    
    def get_uptime(self) -> float:
        """서버 가동 시간 (초)"""
        return time.time() - self.start_time
    
    def check_health(self) -> Dict[str, Any]:
        """시스템 건강 상태 확인"""
        cpu = self.get_cpu_usage()
        memory = self.get_memory_usage()
        disk = self.get_disk_usage()
        
        # 건강 상태 평가
        status = "healthy"
        warnings = []
        
        if cpu > 80:
            status = "warning"
            warnings.append(f"High CPU usage: {cpu:.1f}%")
        
        if memory["percent"] > 85:
            status = "warning"
            warnings.append(f"High memory usage: {memory['percent']:.1f}%")
        
        if disk["percent"] > 90:
            status = "critical"
            warnings.append(f"High disk usage: {disk['percent']:.1f}%")
        
        return {
            "status": status,
            "cpu": cpu,
            "memory": memory["percent"],
            "disk": disk["percent"],
            "uptime": self.get_uptime(),
            "warnings": warnings
        }


class MonitoringMiddleware(BaseHTTPMiddleware):
    """종합 모니터링 미들웨어"""
    
    def __init__(self, app):
        super().__init__(app)
        self.system_monitor = SystemMonitor()
        self.request_log = []
        self.max_log_size = 1000
        self.monitoring_task = None
        
        # 주기적 모니터링은 이벤트 루프가 시작된 후 시작
    
    async def dispatch(self, request: Request, call_next):
        """요청 처리 및 모니터링"""
        # 첫 요청 시 모니터링 태스크 시작
        if self.monitoring_task is None:
            self.monitoring_task = asyncio.create_task(self.periodic_monitoring())
            
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 요청 시작 로깅
        monitoring_state["requests"]["active"] += 1
        monitoring_state["requests"]["total"] += 1
        
        # 요청 정보 수집
        request_info = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", ""),
            "start_time": start_time,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # 요청 처리
            response = await call_next(request)
            
            # 요청 완료 처리
            end_time = time.time()
            duration = end_time - start_time
            
            request_info.update({
                "status_code": response.status_code,
                "duration": duration,
                "end_time": end_time,
                "success": response.status_code < 400
            })
            
            # 성공/실패 카운터 업데이트
            if response.status_code < 400:
                monitoring_state["requests"]["successful"] += 1
            else:
                monitoring_state["requests"]["failed"] += 1
            
            # 응답 시간 기반 로깅
            self.log_request(request_info)
            
        except Exception as e:
            # 에러 처리
            end_time = time.time()
            duration = end_time - start_time
            
            request_info.update({
                "status_code": 500,
                "duration": duration,
                "end_time": end_time,
                "success": False,
                "error": str(e)
            })
            
            monitoring_state["requests"]["failed"] += 1
            self.log_error(request_info, e)
            
            raise
        
        finally:
            monitoring_state["requests"]["active"] -= 1
            self.add_to_request_log(request_info)
        
        return response
    
    def log_request(self, request_info: Dict[str, Any]):
        """요청 로깅"""
        duration_ms = request_info["duration"] * 1000
        
        log_msg = (
            f"[{request_info['request_id'][:8]}] "
            f"{request_info['method']} {request_info['url']} "
            f"-> {request_info['status_code']} "
            f"({duration_ms:.1f}ms)"
        )
        
        # 로그 레벨 결정
        if request_info["status_code"] >= 500:
            monitor_logger.error(log_msg)
        elif request_info["status_code"] >= 400:
            monitor_logger.warning(log_msg)
        elif duration_ms > 1000:
            monitor_logger.warning(f"{log_msg} [SLOW]")
        else:
            monitor_logger.info(log_msg)
    
    def log_error(self, request_info: Dict[str, Any], error: Exception):
        """에러 로깅"""
        error_info = {
            "request_id": request_info["request_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "request_info": request_info
        }
        
        # 에러 로그 저장
        monitoring_state["errors"].append(error_info)
        # 최근 100개 에러만 유지
        monitoring_state["errors"] = monitoring_state["errors"][-100:]
        
        monitor_logger.error(
            f"Request {request_info['request_id'][:8]} failed: {error}"
        )
    
    def add_to_request_log(self, request_info: Dict[str, Any]):
        """요청 로그 저장"""
        self.request_log.append(request_info)
        # 로그 크기 제한
        if len(self.request_log) > self.max_log_size:
            self.request_log = self.request_log[-self.max_log_size:]
    
    async def periodic_monitoring(self):
        """주기적 시스템 모니터링"""
        while True:
            try:
                await asyncio.sleep(30)  # 30초마다 실행
                
                # 시스템 상태 업데이트
                health = self.system_monitor.check_health()
                monitoring_state["system"].update({
                    "cpu_usage": health["cpu"],
                    "memory_usage": health["memory"],
                    "disk_usage": health["disk"],
                    "health_status": health["status"]
                })
                
                # 경고 처리
                if health["warnings"]:
                    for warning in health["warnings"]:
                        alert = {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "level": "warning" if health["status"] == "warning" else "critical",
                            "message": warning
                        }
                        monitoring_state["alerts"].append(alert)
                        monitor_logger.warning(f"System Alert: {warning}")
                
                # 알림 목록 크기 제한
                monitoring_state["alerts"] = monitoring_state["alerts"][-50:]
                
                # 전반적 건강 상태 로깅
                if health["status"] != "healthy":
                    monitor_logger.warning(f"System health: {health['status']}")
                
            except Exception as e:
                monitor_logger.error(f"Monitoring task error: {e}")
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """모니터링 통계 반환"""
        return {
            "requests": monitoring_state["requests"].copy(),
            "system": monitoring_state["system"].copy(),
            "health": self.system_monitor.check_health(),
            "recent_errors": monitoring_state["errors"][-10:],
            "alerts": monitoring_state["alerts"][-10:],
            "uptime": self.system_monitor.get_uptime()
        }
    
    def get_request_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """최근 요청 로그 반환"""
        return self.request_log[-limit:]


# 전역 모니터링 인스턴스
monitoring_instance: Optional[MonitoringMiddleware] = None

def get_monitoring_instance() -> Optional[MonitoringMiddleware]:
    """모니터링 인스턴스 반환"""
    global monitoring_instance
    return monitoring_instance

def set_monitoring_instance(instance: MonitoringMiddleware):
    """모니터링 인스턴스 설정"""
    global monitoring_instance
    monitoring_instance = instance
    print(f"Monitoring instance set: {type(instance).__name__}")