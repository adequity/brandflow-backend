from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.core.config import settings
from app.db.database import create_tables, create_performance_indexes, get_async_db
from app.db.init_data import init_database_data
from app.api.endpoints import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting BrandFlow FastAPI server...")
    
    # 데이터베이스 초기화 (개별 예외 처리)
    try:
        await create_tables()
        print("✅ Database tables created/verified")
    except Exception as e:
        print(f"⚠️ Database table creation failed: {e}")
    
    try:
        await create_performance_indexes()
        print("✅ Performance indexes created/verified")
    except Exception as e:
        print(f"⚠️ Performance index creation failed: {e}")
    
    try:
        from app.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await init_database_data(session)
        print("✅ Initial data created")
    except Exception as e:
        print(f"⚠️ Initial data creation failed: {e}")
    
    print("🎯 BrandFlow server startup completed")
    
    yield
    # Shutdown
    print("🛑 Shutting down BrandFlow server...")


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
# app.add_middleware(RequestSanitizationMiddleware, max_body_size=10*1024*1024)  # 임시 비활성화
# app.add_middleware(RateLimitMiddleware, requests_per_minute=100, requests_per_second=10)  # 임시 비활성화
# app.add_middleware(SecurityHeadersMiddleware)  # 임시 비활성화

# 성능 모니터링 미들웨어 추가 (고급 버전)
# from app.middleware.performance_monitor import PerformanceMiddleware, performance_monitor
# app.add_middleware(PerformanceMiddleware, monitor=performance_monitor)  # 임시 비활성화

# CORS 미들웨어 설정 (보안 강화)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
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
    ],
    expose_headers=["X-Total-Count", "X-Page-Count"],
)

# API 라우터 등록 (기본 auth만 사용)
app.include_router(auth.router, prefix="/api/auth", tags=["인증"])


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

# 테스트 엔드포인트 제거


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )