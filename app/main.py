from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.core.config import settings
from app.db.database import create_tables, create_performance_indexes, get_async_db
from app.db.init_data import init_database_data
# from app.api.router import api_router  # 임시 비활성화
from app.middleware.simple_performance import SimplePerformanceMiddleware
from app.middleware.security import SecurityHeadersMiddleware, RateLimitMiddleware, RequestSanitizationMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting BrandFlow FastAPI server...")
    # await create_tables()
    # print("Database tables created/verified")  # 임시 비활성화
    
    # 성능 최적화 인덱스 생성
    # await create_performance_indexes()
    # print("Performance indexes created/verified")  # 임시 비활성화
    
    # 초기 데이터 생성
    # from app.db.database import AsyncSessionLocal
    # async with AsyncSessionLocal() as session:
    #     await init_database_data(session)  # 임시 비활성화
    
    # 캐시 정리 백그라운드 태스크 시작
    # import asyncio
    # from app.core.cache import cache_cleanup_task
    # asyncio.create_task(cache_cleanup_task())
    # print("Cache cleanup task started")  # 임시 비활성화
    
    # 보안 로깅 시스템 초기화
    # from app.core.logging import setup_application_logging
    # setup_application_logging()
    # print("Security logging system initialized")  # 임시 비활성화
    
    # WebSocket 연결 정리 백그라운드 태스크 시작
    # from app.core.websocket import periodic_cleanup
    # asyncio.create_task(periodic_cleanup())
    # print("WebSocket cleanup task started")  # 임시 비활성화
    
    yield
    # Shutdown
    print("Shutting down BrandFlow server...")


app = FastAPI(
    title="BrandFlow API",
    description="BrandFlow 캠페인 관리 시스템 API",
    version="2.0.0",
    lifespan=lifespan,
    default_response_class=None,  # Enable JSON response configuration
)

# UTF-8 JSON 처리 미들웨어 추가 (가장 먼저 적용)
# from app.middleware.json_utf8 import UTF8JSONMiddleware
# app.add_middleware(UTF8JSONMiddleware)  # 임시 비활성화

# 보안 미들웨어 추가 (순서가 중요 - 가장 먼저 적용)
# from app.middleware.security_audit import SecurityAuditMiddleware
# app.add_middleware(SecurityAuditMiddleware)  # 임시 비활성화
app.add_middleware(RequestSanitizationMiddleware, max_body_size=10*1024*1024)
app.add_middleware(RateLimitMiddleware, requests_per_minute=100, requests_per_second=10)
app.add_middleware(SecurityHeadersMiddleware)

# 성능 모니터링 미들웨어 추가 (고급 버전)
# from app.middleware.performance_monitor import PerformanceMiddleware, performance_monitor
# app.add_middleware(PerformanceMiddleware, monitor=performance_monitor)  # 임시 비활성화

# CORS 미들웨어 설정 (보안 강화)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],  # 필요한 메서드 + OPTIONS for CORS
    allow_headers=[
        "Authorization", 
        "Content-Type", 
        "X-Requested-With",
        "Accept",
        "Origin",
        "User-Agent",
        "Cache-Control",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers"
    ],  # 필요한 헤더만 허용
    expose_headers=["X-Total-Count", "X-Page-Count"],  # 노출할 헤더 제한
)

# API 라우터 등록 (임시로 기본 auth만)
from app.api.endpoints import auth
app.include_router(auth.router, prefix="/api/auth", tags=["인증"])
# app.include_router(api_router, prefix="/api")  # 임시 비활성화


@app.get("/")
async def root():
    return {
        "message": "BrandFlow API v2.0.0 - CORS Fixed",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )