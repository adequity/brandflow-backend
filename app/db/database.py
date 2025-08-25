from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from app.core.config import settings
from app.models.base import Base


# 데이터베이스 URL 가져오기
database_url = settings.get_database_url

# 데이터베이스별 엔진 설정
if database_url.startswith("sqlite"):
    # SQLite용 동기 엔진
    sync_engine = create_engine(
        database_url.replace("sqlite+aiosqlite://", "sqlite://"),
        connect_args={"check_same_thread": False}
    )
    
    # SQLite용 비동기 엔진  
    async_engine = create_async_engine(
        database_url,
        echo=True,
        future=True,
        connect_args={"check_same_thread": False}
    )
elif database_url.startswith("postgresql"):
    # PostgreSQL용 동기 엔진
    sync_engine = create_engine(
        database_url.replace("postgresql+asyncpg://", "postgresql://"),
        pool_pre_ping=True,
        pool_recycle=300,
    )
    
    # PostgreSQL용 비동기 엔진
    async_engine = create_async_engine(
        database_url,
        echo=True,
        future=True,
        pool_pre_ping=True,
        pool_recycle=300,
    )
else:
    raise ValueError(f"Unsupported database URL: {database_url}")

# 세션 생성기
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False,
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


async def get_async_db():
    """비동기 데이터베이스 세션 의존성"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_db():
    """동기 데이터베이스 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def create_tables():
    """데이터베이스 테이블 생성"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_performance_indexes():
    """성능 최적화 인덱스 생성"""
    from app.db.indexes import create_performance_indexes
    await create_performance_indexes(async_engine)