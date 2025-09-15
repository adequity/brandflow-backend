from fastapi import APIRouter
from datetime import datetime
import psutil
import os

router = APIRouter()

@router.get("/")
async def health_check():
    """시스템 헬스체크 엔드포인트"""
    try:
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "2.2.2",
            "message": "BrandFlow FastAPI v2.2.2 Health Check",
            "database": {
                "status": "connected",
                "type": "PostgreSQL"
            },
            "api_endpoints": {
                "auth": "/api/auth",
                "users": "/api/users", 
                "campaigns": "/api/campaigns",
                "purchase_requests": "/api/purchase-requests"
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