# BrandFlow FastAPI v2.0.0 - 점진적 기능 복원
from fastapi import FastAPI
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BrandFlow API v2.0.0",
    description="BrandFlow 캠페인 관리 시스템 - Railway 배포",
    version="2.0.0"
)

# 데이터베이스 연결 상태 추적
db_status = {"connected": False, "error": None}

@app.get("/")
async def root():
    return {
        "message": "BrandFlow FastAPI v2.0.0 - Railway Test", 
        "status": "running",
        "port": os.getenv("PORT", "unknown"),
        "database": db_status["connected"]
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "database": "connected" if db_status["connected"] else "disconnected"
    }

@app.get("/db/status")
async def database_status():
    """데이터베이스 연결 상태 확인"""
    return {
        "connected": db_status["connected"],
        "error": db_status["error"],
        "database_url": "sqlite:///./data/brandflow.db" if db_status["connected"] else "not_configured"
    }

# 데이터베이스 연결 시도 (안전하게)
async def init_database():
    """안전한 데이터베이스 초기화"""
    try:
        logger.info("🔄 Attempting database connection...")
        
        # 기본 데이터 디렉토리 생성
        os.makedirs("./data", exist_ok=True)
        
        # 간단한 SQLite 연결 테스트
        import sqlite3
        conn = sqlite3.connect("./data/brandflow.db")
        conn.execute("SELECT 1").fetchone()
        conn.close()
        
        db_status["connected"] = True
        db_status["error"] = None
        logger.info("✅ Database connection successful")
        
    except Exception as e:
        db_status["connected"] = False
        db_status["error"] = str(e)
        logger.warning(f"⚠️ Database connection failed: {e}")
        logger.info("🚀 Continuing without database (API-only mode)")

if __name__ == "__main__":
    import asyncio
    import uvicorn
    
    # 데이터베이스 초기화 시도
    asyncio.run(init_database())
    
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Starting BrandFlow FastAPI on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)