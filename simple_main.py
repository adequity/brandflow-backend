# BrandFlow FastAPI v2.0.0 - 점진적 기능 복원
from fastapi import FastAPI
from contextlib import asynccontextmanager
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 데이터베이스 연결 상태 추적
db_status = {"connected": False, "error": None, "tables_created": False}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 BrandFlow FastAPI v2.0.0 시작 중...")
    await init_database()
    logger.info("✅ BrandFlow 서버 준비 완료!")
    
    yield
    
    # Shutdown  
    logger.info("🛑 BrandFlow 서버 종료 중...")

app = FastAPI(
    title="BrandFlow API v2.0.0",
    description="BrandFlow 캠페인 관리 시스템 - Railway 배포",
    version="2.0.0",
    lifespan=lifespan
)


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
        "tables_created": db_status["tables_created"],
        "database_url": "sqlite:///./data/brandflow.db" if db_status["connected"] else "not_configured"
    }

# 데이터베이스 연결 시도 (안전하게)
async def init_database():
    """안전한 데이터베이스 초기화"""
    try:
        logger.info("🔄 데이터베이스 연결 시도 중...")
        
        # 기본 데이터 디렉토리 생성
        os.makedirs("./data", exist_ok=True)
        
        # SQLite 연결 및 기본 테이블 생성
        import sqlite3
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 기본 테이블들 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                client_company TEXT,
                budget REAL,
                start_date DATE,
                end_date DATE,
                status TEXT DEFAULT 'active',
                creator_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        
        db_status["connected"] = True
        db_status["tables_created"] = True
        db_status["error"] = None
        logger.info("✅ 데이터베이스 연결 및 테이블 생성 완료")
        
    except Exception as e:
        db_status["connected"] = False
        db_status["tables_created"] = False
        db_status["error"] = str(e)
        logger.warning(f"⚠️ 데이터베이스 초기화 실패: {e}")
        logger.info("🚀 데이터베이스 없이 API 모드로 계속 진행")

if __name__ == "__main__":
    import asyncio
    import uvicorn
    
    # 데이터베이스 초기화 시도
    asyncio.run(init_database())
    
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Starting BrandFlow FastAPI on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)