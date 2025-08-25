from fastapi import APIRouter

from app.api.endpoints import auth, users, campaigns, purchase_requests, dashboard, company_logo, products, notifications, performance, cache, performance_dashboard, security_dashboard, websocket, file_upload, export, search, admin

api_router = APIRouter()

# 인증 라우터
api_router.include_router(auth.router, prefix="/auth", tags=["인증"])

# 사용자 관리 라우터
api_router.include_router(users.router, prefix="/users", tags=["사용자 관리"])

# 캠페인 관리 라우터
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["캠페인 관리"])

# 구매요청 관리 라우터
api_router.include_router(purchase_requests.router, prefix="/purchase-requests", tags=["구매요청"])

# 대시보드 라우터 (AnalyticsService 통합 버전)  
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["대시보드"])

# 회사 로고 관리 라우터
api_router.include_router(company_logo.router, prefix="/company", tags=["회사 로고"])

# 상품 관리 라우터
api_router.include_router(products.router, prefix="/products", tags=["상품 관리"])

# 알림 라우터
api_router.include_router(notifications.router, prefix="/notifications", tags=["알림"])

# 성능 모니터링 라우터
api_router.include_router(performance.router, prefix="/performance", tags=["성능 모니터링"])

# 캐시 관리 라우터
api_router.include_router(cache.router, prefix="/cache", tags=["캐시 관리"])

# 고급 성능 모니터링 라우터
api_router.include_router(performance_dashboard.router, prefix="/performance-dashboard", tags=["성능 대시보드"])

# 보안 대시보드 라우터
api_router.include_router(security_dashboard.router, prefix="/security-dashboard", tags=["보안 대시보드"])

# WebSocket 실시간 알림 라우터
api_router.include_router(websocket.router, prefix="/websocket", tags=["실시간 알림"])

# 파일 업로드 라우터
api_router.include_router(file_upload.router, prefix="/files", tags=["파일 업로드"])

# 데이터 내보내기 라우터
api_router.include_router(export.router, prefix="/export", tags=["데이터 내보내기"])

# 고급 검색 라우터
api_router.include_router(search.router, prefix="/search", tags=["고급 검색"])

# 관리자 전용 라우터
api_router.include_router(admin.router, prefix="/admin", tags=["관리자 전용"])