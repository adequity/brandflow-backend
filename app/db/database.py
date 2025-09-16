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
from app.models.sales import Sales
from app.models.company_logo import CompanyLogo
from app.models.post import Post
from app.models.order_request import OrderRequest


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
        from sqlalchemy import text
        async with async_engine.begin() as conn:
            # 컬럼 존재 여부 확인
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'campaigns' AND column_name = 'client_user_id'
            """))
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("Adding client_user_id column to campaigns table...")
                # 컬럼 추가
                await conn.execute(text("""
                    ALTER TABLE campaigns 
                    ADD COLUMN client_user_id INTEGER REFERENCES users(id)
                """))
                print("✅ client_user_id column added successfully")
            else:
                print("client_user_id column already exists")
                
    except Exception as e:
        print(f"⚠️ Failed to add client_user_id column: {e}")
        # 에러가 발생해도 애플리케이션 시작은 계속 진행


async def migrate_client_company_to_user_id():
    """기존 client_company 데이터를 client_user_id로 마이그레이션"""
    try:
        from sqlalchemy import text
        async with async_engine.begin() as conn:
            print("Starting client_company to client_user_id migration...")
            
            # client_company에서 (ID: user_id) 패턴 추출하여 client_user_id 업데이트
            result = await conn.execute(text("""
                UPDATE campaigns 
                SET client_user_id = CAST(
                    SUBSTRING(client_company FROM '\\(ID: (\\d+)\\)') AS INTEGER
                )
                WHERE client_company LIKE '%(ID: %)' 
                AND client_user_id IS NULL
            """))
            
            updated_count = result.rowcount
            print(f"✅ Successfully migrated {updated_count} campaigns with client_user_id")
            
            # 마이그레이션 결과 확인 (컬럼 존재 여부 다시 확인)
            column_check = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'campaigns' AND column_name = 'client_user_id'
            """))
            column_exists_after = column_check.fetchone() is not None
            
            if column_exists_after:
                check_result = await conn.execute(text("""
                    SELECT COUNT(*) as total_campaigns,
                           COUNT(client_user_id) as with_client_user_id,
                           COUNT(CASE WHEN client_company LIKE '%(ID: %)' THEN 1 END) as with_id_pattern
                    FROM campaigns
                """))
                stats = check_result.fetchone()
                print(f"Migration stats: {stats.total_campaigns} total campaigns, "
                      f"{stats.with_client_user_id} with client_user_id, "
                      f"{stats.with_id_pattern} with ID pattern")
            else:
                print("Warning: client_user_id column still not found after migration")
                
    except Exception as e:
        print(f"⚠️ Failed to migrate client_company data: {e}")
        # 에러가 발생해도 애플리케이션 시작은 계속 진행


async def add_campaign_date_columns():
    """campaigns 테이블에 start_date, end_date 컬럼 추가"""
    try:
        from sqlalchemy import text
        from datetime import datetime
        async with async_engine.begin() as conn:
            # 현재 컬럼 확인
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'campaigns' AND column_name IN ('start_date', 'end_date')
            """))
            existing_columns = {row[0] for row in result.fetchall()}
            
            # start_date 컬럼 추가
            if 'start_date' not in existing_columns:
                print("Adding start_date column to campaigns table...")
                await conn.execute(text("""
                    ALTER TABLE campaigns 
                    ADD COLUMN start_date TIMESTAMP
                """))
                print("✅ start_date column added successfully")
            else:
                print("start_date column already exists")
            
            # end_date 컬럼 추가
            if 'end_date' not in existing_columns:
                print("Adding end_date column to campaigns table...")
                await conn.execute(text("""
                    ALTER TABLE campaigns 
                    ADD COLUMN end_date TIMESTAMP
                """))
                print("✅ end_date column added successfully")
            else:
                print("end_date column already exists")
            
            # 기존 데이터에 기본값 설정 (NULL인 경우만)
            if 'start_date' not in existing_columns or 'end_date' not in existing_columns:
                current_time = datetime.now()
                await conn.execute(text("""
                    UPDATE campaigns 
                    SET start_date = COALESCE(start_date, :current_time),
                        end_date = COALESCE(end_date, :current_time + INTERVAL '30 days')
                    WHERE start_date IS NULL OR end_date IS NULL
                """), {"current_time": current_time})
                
                # 컬럼을 NOT NULL로 변경
                await conn.execute(text("ALTER TABLE campaigns ALTER COLUMN start_date SET NOT NULL"))
                await conn.execute(text("ALTER TABLE campaigns ALTER COLUMN end_date SET NOT NULL"))
                print("✅ Set start_date and end_date columns to NOT NULL with default values")
                
    except Exception as e:
        print(f"⚠️ Failed to add campaign date columns: {e}")
        # 에러가 발생해도 애플리케이션 시작은 계속 진행


async def update_null_campaign_dates():
    """NULL인 캠페인 날짜 필드들에 기본값 설정"""
    try:
        from sqlalchemy import text
        from datetime import datetime, timedelta
        
        async with async_engine.begin() as conn:
            print("Updating NULL campaign dates with default values...")
            
            # NULL인 start_date와 end_date를 가진 캠페인 수 확인
            result = await conn.execute(text("""
                SELECT COUNT(*) 
                FROM campaigns 
                WHERE start_date IS NULL OR end_date IS NULL
            """))
            null_count = result.scalar()
            
            if null_count > 0:
                print(f"Found {null_count} campaigns with NULL dates")
                
                # NULL인 날짜 필드들을 현재 시간과 30일 후로 설정
                current_time = datetime.now()
                end_time = current_time + timedelta(days=30)
                
                await conn.execute(text("""
                    UPDATE campaigns 
                    SET start_date = COALESCE(start_date, :start_date),
                        end_date = COALESCE(end_date, :end_date)
                    WHERE start_date IS NULL OR end_date IS NULL
                """), {
                    'start_date': current_time,
                    'end_date': end_time
                })
                
                print(f"Updated {null_count} campaigns with default dates")
                print(f"Default start_date: {current_time}")
                print(f"Default end_date: {end_time}")
            else:
                print("All campaigns already have date values")
                
    except Exception as e:
        print(f"⚠️ Failed to update NULL campaign dates: {e}")