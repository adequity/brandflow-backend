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
    # Startup
    print("Starting BrandFlow FastAPI server...")
    
    # 데이터베이스 초기화 (개별 예외 처리)
    try:
        await create_tables()
        print("Database tables created/verified")
    except Exception as e:
        print(f"Database table creation failed: {e}")
    
    try:
        await create_performance_indexes()
        print("Performance indexes created/verified")
    except Exception as e:
        print(f"Performance index creation failed: {e}")
    
    try:
        from app.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await init_database_data(session)
        print("Initial data created")
    except Exception as e:
        print(f"Initial data creation failed: {e}")
    
    print("BrandFlow server startup completed")
    
    yield
    # Shutdown
    print("Shutting down BrandFlow server...")


app = FastAPI(
    title="BrandFlow API",
    description="BrandFlow 캠페인 관리 시스템 API",
    version="2.0.0",
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

# 모니터링 미들웨어 추가
from app.middleware.monitoring import MonitoringMiddleware, set_monitoring_instance

# 모니터링 미들웨어 인스턴스 생성 및 등록
monitoring_middleware_instance = MonitoringMiddleware(app)
app.add_middleware(MonitoringMiddleware)
set_monitoring_instance(monitoring_middleware_instance)

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