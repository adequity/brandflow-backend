# BrandFlow FastAPI v2.0.0 - 점진적 기능 복원
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
from pydantic import BaseModel
import os
import logging
import hashlib
import sqlite3
import jwt
import datetime
from typing import Optional

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