from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.core.config import settings
from app.db.database import create_tables, create_performance_indexes, get_async_db
from app.db.init_data import init_database_data
from app.api.endpoints import auth, users, campaigns, purchase_requests, company_logo, notifications, file_upload, performance, monitoring


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Railway 배포용 단순화
    print("🚀 Starting BrandFlow FastAPI v2.2.2...")
    print("🌐 Railway deployment mode - Health API enabled")
    
    # 데이터베이스 초기화 실행
    try:
        print("🔄 Creating database tables...")
        await create_tables()
        print("✅ Database tables created")
        
        print("🔄 Initializing test data...")
        # 데이터베이스 세션을 사용하여 초기화 데이터 생성
        async for db in get_async_db():
            await init_database_data(db)
            break  # 첫 번째 세션만 사용
        print("✅ Database initialization completed")
    except Exception as e:
        print(f"⚠️ Database initialization failed: {str(e)}")
        import traceback
        print(f"Full error: {traceback.format_exc()}")
        # 초기화 실패해도 서버는 계속 실행
        pass
    print("✅ BrandFlow FastAPI v2.2.2 ready!")
    
    yield
    # Shutdown
    print("🛑 BrandFlow server shutdown completed")


app = FastAPI(
    title="BrandFlow API",
    description="BrandFlow 캠페인 관리 시스템 API",
    version="2.2.2",
    lifespan=lifespan,
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

# 모니터링 미들웨어 추가 (Railway 배포 시 임시 비활성화)
# from app.middleware.monitoring import MonitoringMiddleware, set_monitoring_instance

# 모니터링 미들웨어 인스턴스 생성 및 등록 (임시 비활성화)
# monitoring_middleware_instance = MonitoringMiddleware(app)
# app.add_middleware(MonitoringMiddleware)
# set_monitoring_instance(monitoring_middleware_instance)

# HTTPS 리다이렉트 미들웨어 추가 (Mixed Content 방지)
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
# Railway 환경에서만 HTTPS 강제 (로컬 개발 환경은 제외)
import os
if os.getenv('RAILWAY_ENVIRONMENT_NAME') or os.getenv('PORT'):
    app.add_middleware(HTTPSRedirectMiddleware)
    print("🔒 HTTPS 리다이렉트 미들웨어 활성화")

# 성능 모니터링 미들웨어 추가
from app.middleware.simple_performance import SimplePerformanceMiddleware
app.add_middleware(SimplePerformanceMiddleware)

# CORS 미들웨어 설정 (개발 환경용 - 모든 origin 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 환경용 - 모든 origin 허용
    allow_credentials=False,  # allow_origins=["*"]일 때는 False여야 함
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],  # 모든 헤더 허용
    expose_headers=["X-Total-Count", "X-Page-Count"],
)

# API 라우터 등록
app.include_router(auth.router, prefix="/api/auth", tags=["인증"])
app.include_router(users.router, prefix="/api/users", tags=["사용자"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["캠페인"])
app.include_router(purchase_requests.router, prefix="/api/purchase-requests", tags=["구매요청"])
app.include_router(company_logo.router, prefix="/api/company", tags=["회사"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["알림"])
app.include_router(file_upload.router, prefix="/api/files", tags=["파일"])
app.include_router(performance.router, prefix="/api/performance", tags=["성능"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["모니터링"])


@app.get("/")
async def root():
    return {
        "message": "BrandFlow API v2.2.2 - Health API Ready",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.2.2",
        "message": "BrandFlow FastAPI Health Check",
        "timestamp": "2025-08-28T10:30:00Z"
    }

# 테스트 엔드포인트 제거


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )