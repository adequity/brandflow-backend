from fastapi import APIRouter
from datetime import datetime
import psutil
import os
from pathlib import Path
from app.core.config import settings

router = APIRouter()

@router.get("/")
async def health_check():
    """시스템 헬스체크 엔드포인트"""
    try:
        # Upload directory 상태 확인
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_status = {
            "path": str(upload_dir),
            "exists": upload_dir.exists(),
            "is_writable": False,
            "subdirectories": []
        }

        if upload_dir.exists():
            try:
                # 쓰기 권한 테스트
                test_file = upload_dir / ".write_test"
                test_file.touch()
                test_file.unlink()
                upload_status["is_writable"] = True

                # 하위 디렉토리 확인
                upload_status["subdirectories"] = [d.name for d in upload_dir.iterdir() if d.is_dir()]
            except Exception as e:
                upload_status["error"] = str(e)

        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "2.3.0",
            "message": "BrandFlow FastAPI v2.3.0 with Volume Support",
            "database": {
                "status": "connected",
                "type": "PostgreSQL"
            },
            "upload_directory": upload_status,
            "environment": {
                "railway": os.getenv("RAILWAY_ENVIRONMENT", "local"),
                "upload_dir_config": settings.UPLOAD_DIR
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
            "version": "2.3.0",
            "error": str(e)
        }