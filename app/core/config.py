from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Database Configuration - Railway와 로컬 환경 모두 지원
    DATABASE_URL: str = "sqlite+aiosqlite:///./database.sqlite"  # 안전한 기본값
    
    # PostgreSQL specific settings
    POSTGRES_USER: Optional[str] = "brandflow_user"
    POSTGRES_PASSWORD: Optional[str] = "brandflow_password_2024"
    POSTGRES_DB: Optional[str] = "brandflow"
    POSTGRES_HOST: Optional[str] = "localhost"
    POSTGRES_PORT: Optional[int] = 5432
    
    @property
    def get_database_url(self) -> str:
        """Railway PostgreSQL 우선 사용 - 헬스체크 비활성화로 안정성 확보"""
        # Railway 환경에서 DATABASE_URL 환경변수 우선 사용
        railway_db_url = os.getenv("DATABASE_URL")
        if railway_db_url:
            # Railway PostgreSQL URL 변환 및 사용
            if railway_db_url.startswith("postgres://"):
                railway_db_url = railway_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
            return railway_db_url
        
        # 로컬 개발 환경: PostgreSQL 설정 확인
        if os.getenv("USE_POSTGRESQL", "false").lower() == "true":
            return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
        # SQLite fallback (Railway에서 DATABASE_URL이 없는 경우)
        return "sqlite+aiosqlite:///./database.sqlite"
    
    # Security
    SECRET_KEY: str = "brandflow-production-secret-key-2024-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Application settings
    DEBUG: bool = False  # Production mode
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",  # Vite dev server alternative port
        "http://localhost:5175",  # Vite dev server alternative port 2
        "http://localhost:5176",  # Vite dev server alternative port 3
        "http://localhost:5177",  # Vite dev server alternative port 4
        "http://localhost:5178",  # Vite dev server alternative port 5
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:5177",
        "http://127.0.0.1:5178",
        "https://brandflo.netlify.app"  # Production frontend URL
    ]
    
    # Alternative CORS_ORIGINS for compatibility
    CORS_ORIGINS: Optional[str] = None
    
    # File Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10485760  # 10MB
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 추가 필드 무시


settings = Settings()