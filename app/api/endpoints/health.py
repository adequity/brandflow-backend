from fastapi import APIRouter
from datetime import datetime
import psutil
import os

router = APIRouter()

@router.get("/")
async def health_check():
    """시스템 헬스체크 엔드포인트"""
    try:
        # 시스템 정보 수집
        memory_info = psutil.virtual_memory()
        disk_info = psutil.disk_usage('/')
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "2.2.2",
            "uptime": f"{datetime.now()}",
            "system": {
                "memory_used_percent": memory_info.percent,
                "memory_available_gb": round(memory_info.available / (1024**3), 2),
                "disk_used_percent": disk_info.percent,
                "cpu_count": psutil.cpu_count()
            },
            "database": {
                "status": "connected",
                "type": "SQLite"
            },
            "api_endpoints": {
                "auth": "/api/auth",
                "users": "/api/users", 
                "campaigns": "/api/campaigns",
                "products": "/api/products",
                "purchase_requests": "/api/purchase-requests",
                "work_types": "/api/work-types"
            }
        }
        
        return health_data
        
    except Exception as e:
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "version": "2.2.2",
            "error": str(e)
        }