from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Database Configuration - PostgreSQL 전용
    DATABASE_URL: str = "postgresql+asyncpg://brandflow_user:brandflow_password_2024@localhost:5432/brandflow"  # PostgreSQL 기본값
    
    # PostgreSQL specific settings
    POSTGRES_USER: Optional[str] = "brandflow_user"
    POSTGRES_PASSWORD: Optional[str] = "brandflow_password_2024"
    POSTGRES_DB: Optional[str] = "brandflow"
    POSTGRES_HOST: Optional[str] = "localhost"
    POSTGRES_PORT: Optional[int] = 5432
    
    @property
    def get_database_url(self) -> str:
        """Railway PostgreSQL 연결 URL 반환"""
        # 1순위: 환경변수 DATABASE_URL (Railway 배포 환경)
        railway_env_url = os.getenv("DATABASE_URL")
        if railway_env_url:
            if railway_env_url.startswith("postgresql://"):
                railway_env_url = railway_env_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            print(f"Using Railway Environment DATABASE_URL")
            return railway_env_url

        # 2순위: .env 파일의 DATABASE_URL
        if hasattr(self, 'DATABASE_URL') and self.DATABASE_URL:
            env_url = self.DATABASE_URL
            if env_url.startswith("postgresql://"):
                env_url = env_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            print(f"Using .env DATABASE_URL")
            return env_url

        # 3순위: 최신 Railway 폴백
        railway_url = "postgresql+asyncpg://postgres:kAPUkGlWqoHwxIvtWaeukQuwcrZpSzuu@maglev.proxy.rlwy.net:32077/railway"
        print(f"Using Railway PostgreSQL fallback")
        return railway_url
    
    # Security
    SECRET_KEY: str = "brandflow-production-secret-key-2024-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8시간 (업무 시간 동안 끊김 없음)
    
    # Application settings
    DEBUG: bool = False  # Production mode

    # File Storage
    UPLOAD_DIR: str = "/app/data/uploads"  # Railway Volume 마운트 경로

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
    UPLOAD_DIR: str = "/app/data/uploads" if os.getenv("RAILWAY_ENVIRONMENT") else "./uploads"
    MAX_FILE_SIZE: int = 10485760  # 10MB
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 추가 필드 무시


settings = Settings()