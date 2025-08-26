# BrandFlow FastAPI v2.0.0 - 점진적 기능 복원
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import os
import logging
import hashlib
import sqlite3
import jwt
import datetime
import time
import psutil
import sys
from typing import Optional, Dict, Any

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JWT 설정
SECRET_KEY = os.getenv("JWT_SECRET", "brandflow-test-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 인증 스키마
security = HTTPBearer()

# 데이터베이스 연결 상태 추적
db_status = {"connected": False, "error": None, "tables_created": False}

# 모니터링 상태 추적
monitoring_stats = {
    "requests_count": 0,
    "total_processing_time": 0,
    "start_time": time.time(),
    "errors_count": 0
}

# Pydantic 모델들
class LoginRequest(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "user"

class Token(BaseModel):
    access_token: str
    token_type: str

class CampaignCreate(BaseModel):
    name: str
    description: str = ""
    client_company: str = ""
    budget: float = 0.0
    start_date: str = ""
    end_date: str = ""
    status: str = "active"

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_company: Optional[str] = None
    budget: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None

# 인증 헬퍼 함수들
def hash_password(password: str) -> str:
    """비밀번호 해시화"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    """JWT 토큰 생성"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user_by_email(email: str) -> Optional[dict]:
    """이메일로 사용자 조회"""
    if not db_status["connected"]:
        return None
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, hashed_password, role FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        if user:
            return {
                "id": user[0],
                "name": user[1],
                "email": user[2],
                "hashed_password": user[3],
                "role": user[4]
            }
        return None
    except Exception as e:
        logger.error(f"사용자 조회 오류: {e}")
        return None

def create_user(user_data: UserCreate) -> bool:
    """새 사용자 생성"""
    if not db_status["connected"]:
        return False
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, hashed_password, role) VALUES (?, ?, ?, ?)",
            (user_data.name, user_data.email, hash_password(user_data.password), user_data.role)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"사용자 생성 오류: {e}")
        return False

# 모니터링 헬퍼 함수들
def get_system_info() -> Dict[str, Any]:
    """시스템 정보 조회"""
    try:
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "uptime": time.time() - monitoring_stats["start_time"]
        }
    except Exception as e:
        logger.error(f"시스템 정보 조회 오류: {e}")
        return {"error": str(e)}

def get_database_stats() -> Dict[str, Any]:
    """데이터베이스 통계 조회"""
    if not db_status["connected"]:
        return {"error": "Database not connected"}
    
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 사용자 수
        cursor.execute("SELECT COUNT(*) FROM users")
        users_count = cursor.fetchone()[0]
        
        # 캠페인 수
        cursor.execute("SELECT COUNT(*) FROM campaigns")
        campaigns_count = cursor.fetchone()[0]
        
        # 활성 캠페인 수
        cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'active'")
        active_campaigns = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "users_count": users_count,
            "campaigns_count": campaigns_count,
            "active_campaigns": active_campaigns
        }
    except Exception as e:
        logger.error(f"데이터베이스 통계 조회 오류: {e}")
        return {"error": str(e)}

# 캠페인 CRUD 헬퍼 함수들
def create_campaign(campaign_data: CampaignCreate, creator_id: int) -> Optional[int]:
    """새 캠페인 생성"""
    if not db_status["connected"]:
        return None
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO campaigns (name, description, client_company, budget, 
                                 start_date, end_date, status, creator_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            campaign_data.name, campaign_data.description, campaign_data.client_company,
            campaign_data.budget, campaign_data.start_date, campaign_data.end_date,
            campaign_data.status, creator_id
        ))
        campaign_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return campaign_id
    except Exception as e:
        logger.error(f"캠페인 생성 오류: {e}")
        return None

def update_campaign(campaign_id: int, campaign_data: CampaignUpdate) -> bool:
    """캠페인 업데이트"""
    if not db_status["connected"]:
        return False
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 업데이트할 필드들만 처리
        update_fields = []
        params = []
        
        for field, value in campaign_data.dict(exclude_none=True).items():
            update_fields.append(f"{field} = ?")
            params.append(value)
        
        if not update_fields:
            return True  # 업데이트할 내용이 없으면 성공으로 처리
        
        params.append(campaign_id)
        query = f"UPDATE campaigns SET {', '.join(update_fields)} WHERE id = ?"
        
        cursor.execute(query, params)
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        
        return affected_rows > 0
    except Exception as e:
        logger.error(f"캠페인 업데이트 오류: {e}")
        return False

def delete_campaign(campaign_id: int) -> bool:
    """캠페인 삭제"""
    if not db_status["connected"]:
        return False
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        return affected_rows > 0
    except Exception as e:
        logger.error(f"캠페인 삭제 오류: {e}")
        return False

def get_campaign_by_id(campaign_id: int) -> Optional[dict]:
    """ID로 캠페인 조회"""
    if not db_status["connected"]:
        return None
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, u.name as creator_name 
            FROM campaigns c 
            LEFT JOIN users u ON c.creator_id = u.id
            WHERE c.id = ?
        """, (campaign_id,))
        campaign = cursor.fetchone()
        conn.close()
        
        if campaign:
            return {
                "id": campaign[0],
                "name": campaign[1],
                "description": campaign[2],
                "client_company": campaign[3],
                "budget": campaign[4],
                "start_date": campaign[5],
                "end_date": campaign[6],
                "status": campaign[7],
                "creator_id": campaign[8],
                "created_at": campaign[9],
                "creator_name": campaign[10]
            }
        return None
    except Exception as e:
        logger.error(f"캠페인 조회 오류: {e}")
        return None

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

# CORS 미들웨어 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React 개발 서버
        "http://localhost:5173",  # Vite 개발 서버
        "https://brandflow-frontend.vercel.app",  # 프로덕션 프론트엔드
        "https://web-production-f12ef.up.railway.app"  # 자체 도메인
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Page-Count"]
)

# 보안 미들웨어
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=[
        "web-production-f12ef.up.railway.app",
        "localhost", 
        "127.0.0.1",
        "*.railway.app"
    ]
)

# 보안 헤더 미들웨어
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# 요청 로깅 및 통계 미들웨어  
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # 통계 업데이트
        monitoring_stats["requests_count"] += 1
        monitoring_stats["total_processing_time"] += process_time
        
        if response.status_code >= 400:
            monitoring_stats["errors_count"] += 1
        
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        return response
    except Exception as e:
        monitoring_stats["errors_count"] += 1
        logger.error(f"Request failed: {e}")
        raise

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

# 인증 API 엔드포인트들
@app.post("/api/auth/login-json", response_model=Token)
async def login(login_request: LoginRequest):
    """사용자 로그인"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # 사용자 확인
    user = get_user_by_email(login_request.email)
    if not user or user["hashed_password"] != hash_password(login_request.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # JWT 토큰 생성
    access_token = create_access_token(
        data={"sub": user["email"], "user_id": user["id"], "role": user["role"]}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@app.post("/api/auth/register")
async def register(user_data: UserCreate):
    """사용자 회원가입"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # 이메일 중복 확인
    existing_user = get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # 사용자 생성
    if create_user(user_data):
        return {"message": "User created successfully", "email": user_data.email}
    else:
        raise HTTPException(status_code=500, detail="Failed to create user")

@app.get("/api/auth/me")
async def get_current_user(token: str = Depends(security)):
    """현재 사용자 정보 조회"""
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = get_user_by_email(email)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# 비즈니스 로직 API 엔드포인트들
@app.get("/api/users")
async def get_users():
    """사용자 목록 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, role, created_at FROM users")
        users = cursor.fetchall()
        conn.close()
        
        return {
            "users": [
                {
                    "id": user[0],
                    "name": user[1], 
                    "email": user[2],
                    "role": user[3],
                    "created_at": user[4]
                } for user in users
            ],
            "count": len(users)
        }
    except Exception as e:
        logger.error(f"사용자 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@app.get("/api/campaigns")
async def get_campaigns():
    """캠페인 목록 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, u.name as creator_name 
            FROM campaigns c 
            LEFT JOIN users u ON c.creator_id = u.id
        """)
        campaigns = cursor.fetchall()
        conn.close()
        
        return {
            "campaigns": [
                {
                    "id": campaign[0],
                    "name": campaign[1],
                    "description": campaign[2],
                    "client_company": campaign[3],
                    "budget": campaign[4],
                    "start_date": campaign[5],
                    "end_date": campaign[6],
                    "status": campaign[7],
                    "creator_id": campaign[8],
                    "created_at": campaign[9],
                    "creator_name": campaign[10]
                } for campaign in campaigns
            ],
            "count": len(campaigns)
        }
    except Exception as e:
        logger.error(f"캠페인 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch campaigns")

@app.post("/api/campaigns")
async def create_new_campaign(campaign_data: CampaignCreate, token: str = Depends(security)):
    """새 캠페인 생성"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 정보 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 캠페인 생성
    campaign_id = create_campaign(campaign_data, user_id)
    if campaign_id:
        # 생성된 캠페인 정보 반환
        campaign = get_campaign_by_id(campaign_id)
        return {"message": "Campaign created successfully", "campaign": campaign}
    else:
        raise HTTPException(status_code=500, detail="Failed to create campaign")

@app.get("/api/campaigns/{campaign_id}")
async def get_campaign_detail(campaign_id: int):
    """캠페인 상세 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    campaign = get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return campaign

@app.put("/api/campaigns/{campaign_id}")
async def update_campaign_detail(
    campaign_id: int, 
    campaign_data: CampaignUpdate, 
    token: str = Depends(security)
):
    """캠페인 업데이트"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰 검증 
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 캠페인 존재 확인
    existing_campaign = get_campaign_by_id(campaign_id)
    if not existing_campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # 권한 확인 (작성자 또는 관리자만)
    if existing_campaign["creator_id"] != user_id:
        # 관리자 권한 확인
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Permission denied")
    
    # 캠페인 업데이트
    if update_campaign(campaign_id, campaign_data):
        updated_campaign = get_campaign_by_id(campaign_id)
        return {"message": "Campaign updated successfully", "campaign": updated_campaign}
    else:
        raise HTTPException(status_code=500, detail="Failed to update campaign")

@app.delete("/api/campaigns/{campaign_id}")
async def delete_campaign_by_id(campaign_id: int, token: str = Depends(security)):
    """캠페인 삭제"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰 검증
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 캠페인 존재 확인
    existing_campaign = get_campaign_by_id(campaign_id)
    if not existing_campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # 권한 확인 (작성자 또는 관리자만)
    if existing_campaign["creator_id"] != user_id:
        # 관리자 권한 확인
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Permission denied")
    
    # 캠페인 삭제
    if delete_campaign(campaign_id):
        return {"message": "Campaign deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete campaign")

# 모니터링 API 엔드포인트들
@app.get("/api/monitoring/health")
async def monitoring_health():
    """종합 헬스체크"""
    system_info = get_system_info()
    db_stats = get_database_stats()
    
    # 헬스 상태 판단
    health_status = "healthy"
    issues = []
    
    if "error" in system_info:
        health_status = "degraded"
        issues.append("System monitoring unavailable")
    else:
        if system_info.get("cpu_percent", 0) > 80:
            health_status = "degraded" 
            issues.append("High CPU usage")
        if system_info.get("memory_percent", 0) > 85:
            health_status = "degraded"
            issues.append("High memory usage")
    
    if not db_status["connected"]:
        health_status = "unhealthy" if health_status == "healthy" else "critical"
        issues.append("Database disconnected")
    
    return {
        "status": health_status,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "uptime": time.time() - monitoring_stats["start_time"],
        "database": {
            "connected": db_status["connected"],
            "tables_created": db_status["tables_created"],
            "stats": db_stats
        },
        "system": system_info,
        "issues": issues
    }

@app.get("/api/performance/stats")
async def performance_stats():
    """성능 통계 조회"""
    uptime = time.time() - monitoring_stats["start_time"]
    avg_response_time = (
        monitoring_stats["total_processing_time"] / monitoring_stats["requests_count"] 
        if monitoring_stats["requests_count"] > 0 else 0
    )
    
    system_info = get_system_info()
    
    return {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "uptime_seconds": uptime,
        "requests": {
            "total": monitoring_stats["requests_count"],
            "errors": monitoring_stats["errors_count"],
            "error_rate": (
                monitoring_stats["errors_count"] / monitoring_stats["requests_count"] * 100
                if monitoring_stats["requests_count"] > 0 else 0
            )
        },
        "response_time": {
            "total": monitoring_stats["total_processing_time"],
            "average": avg_response_time
        },
        "system": system_info,
        "database": get_database_stats()
    }

@app.get("/api/monitoring/status") 
async def monitoring_status():
    """간단한 상태 확인"""
    return {
        "api": "operational",
        "database": "operational" if db_status["connected"] else "down",
        "uptime": time.time() - monitoring_stats["start_time"],
        "requests_handled": monitoring_stats["requests_count"]
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
        
        # 기본 테스트 사용자 생성 (존재하지 않는 경우만)
        cursor.execute("SELECT COUNT(*) FROM users WHERE email = ?", ("test@brandflow.com",))
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO users (name, email, hashed_password, role) VALUES (?, ?, ?, ?)",
                ("테스트 사용자", "test@brandflow.com", hash_password("test123"), "admin")
            )
            conn.commit()
            logger.info("✅ 기본 테스트 사용자 생성: test@brandflow.com / test123")
        
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