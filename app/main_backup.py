from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.core.config import settings
from app.db.database import create_tables, create_performance_indexes, get_async_db
from app.db.init_data import init_database_data
from app.api.endpoints import auth, users, campaigns, purchase_requests, company_logo, products, work_types, notifications, file_upload, performance, monitoring


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Railway 배포용 단순화
    print("Starting BrandFlow FastAPI v2.2.2...")
    print("Railway deployment mode - Health API enabled")
    
    # 데이터베이스 초기화 실행
    try:
        print("Creating database tables...")
        await create_tables()
        print("Database tables created")
        
        print("Skipping data initialization - using existing database...")
        # 기존 데이터베이스 사용, 초기화 데이터 생성 비활성화
        # async for db in get_async_db():
        #     await init_database_data(db)
        #     break  # 첫 번째 세션만 사용
        print("Using existing database data")
    except Exception as e:
        print(f"WARNING: Database initialization failed: {str(e)}")
        import traceback
        print(f"Full error: {traceback.format_exc()}")
        # 초기화 실패해도 서버는 계속 실행
        pass
    print("BrandFlow FastAPI v2.2.2 ready!")
    
    yield
    # Shutdown
    print("BrandFlow server shutdown completed")


app = FastAPI(
    title="BrandFlow API",
    description="BrandFlow 캠페인 관리 시스템 API",
    version="2.2.2",
    lifespan=lifespan,
)

# UTF-8 JSON 처리 미들웨어 추가 (가장 먼저 적용)
# SimpleCORSMiddleware 제거 - CORSMiddleware와 중복 방지
# from app.middleware.simple_cors import SimpleCORSMiddleware
# app.add_middleware(SimpleCORSMiddleware)  # CORSMiddleware와 중복되어 비활성화

# from app.middleware.json_utf8 import UTF8JSONMiddleware
# app.add_middleware(UTF8JSONMiddleware)  # WARNING: 2분 타임아웃 문제로 재비활성화

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
# Railway 헬스체크 실패 방지를 위해 임시 비활성화
# from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
# Railway 환경에서만 HTTPS 강제 (로컬 개발 환경은 제외)
import os
# if os.getenv('RAILWAY_ENVIRONMENT_NAME') or os.getenv('PORT'):
#     app.add_middleware(HTTPSRedirectMiddleware)
#     print("HTTPS 리다이렉트 미들웨어 활성화")

# 성능 모니터링 미들웨어 추가
from app.middleware.simple_performance import SimplePerformanceMiddleware
app.add_middleware(SimplePerformanceMiddleware)

# CORS 미들웨어 설정 (프로덕션 보안 강화)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://brandflo.netlify.app",  # 메인 Netlify 도메인
        "http://localhost:3000",        # 로컬 개발
        "http://localhost:5173",        # Vite 개발 서버
        "http://127.0.0.1:3000",        # 로컬 IP 개발
        "http://127.0.0.1:5173"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["X-Total-Count", "X-Page-Count"],
)

# API 라우터 등록
app.include_router(auth.router, prefix="/api/auth", tags=["인증"])
app.include_router(users.router, prefix="/api/users", tags=["사용자"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["캠페인"])
app.include_router(purchase_requests.router, prefix="/api/purchase-requests", tags=["구매요청"])
app.include_router(company_logo.router, prefix="/api/company", tags=["회사"])
app.include_router(products.router, prefix="/api/products", tags=["상품"])
app.include_router(work_types.router, prefix="/api/work-types", tags=["작업유형"])
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