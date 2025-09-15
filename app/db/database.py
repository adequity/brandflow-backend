from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from app.core.config import settings
from app.models.base import Base
# 모든 모델을 import하여 테이블 생성 보장
from app.models.user import User
from app.models.campaign import Campaign
from app.models.purchase_request import PurchaseRequest
from app.models.product import Product
from app.models.work_type import WorkType


# Railway PostgreSQL 데이터베이스 URL 가져오기
database_url = settings.get_database_url  # 프로퍼티 호출

# Railway PostgreSQL 전용 엔진 설정
print(f"Database URL: {database_url}")

# PostgreSQL용 동기 엔진
sync_engine = create_engine(
    database_url.replace("postgresql+asyncpg://", "postgresql://"),
    pool_pre_ping=True,
    pool_recycle=300,
    echo=True
)

# PostgreSQL용 비동기 엔진
async_engine = create_async_engine(
    database_url,
    echo=True,
    future=True,
    pool_pre_ping=True,
    pool_recycle=300,
)

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


async def add_client_user_id_column():
    """campaigns 테이블에 client_user_id 컬럼 추가"""
    try:
        async with async_engine.begin() as conn:
            # 컬럼 존재 여부 확인
            result = await conn.execute(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'campaigns' AND column_name = 'client_user_id'
                """
            )
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("Adding client_user_id column to campaigns table...")
                # 컬럼 추가
                await conn.execute(
                    """
                    ALTER TABLE campaigns 
                    ADD COLUMN client_user_id INTEGER REFERENCES users(id)
                    """
                )
                print("✅ client_user_id column added successfully")
            else:
                print("client_user_id column already exists")
                
    except Exception as e:
        print(f"⚠️ Failed to add client_user_id column: {e}")
        # 에러가 발생해도 애플리케이션 시작은 계속 진행