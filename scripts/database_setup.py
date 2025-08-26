"""
데이터베이스 설정 및 초기화 스크립트
"""

import asyncio
import os
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.db.database import async_engine, create_tables, create_performance_indexes
from app.core.config import settings


async def setup_database():
    """데이터베이스 초기 설정"""
    print("데이터베이스 설정 시작...")
    
    try:
        # 1. 테이블 생성
        print("데이터베이스 테이블 생성 중...")
        await create_tables()
        print("테이블 생성 완료")
        
        # 2. 성능 인덱스 생성
        print("성능 최적화 인덱스 생성 중...")
        await create_performance_indexes()
        print("인덱스 생성 완료")
        
        # 3. 데이터베이스 상태 확인
        await check_database_status()
        
        print("데이터베이스 설정 완료!")
        
    except Exception as e:
        print(f"데이터베이스 설정 오류: {e}")
        raise


async def check_database_status():
    """데이터베이스 상태 확인"""
    from sqlalchemy import text
    
    async with async_engine.begin() as conn:
        # 테이블 목록 조회
        if settings.get_database_url.startswith("sqlite"):
            result = await conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """))
        else:  # PostgreSQL
            result = await conn.execute(text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """))
        
        tables = result.fetchall()
        
        print("\n데이터베이스 상태:")
        print(f"   데이터베이스 URL: {settings.get_database_url}")
        print(f"   테이블 수: {len(tables)}")
        
        for table in tables:
            table_name = table[0]
            
            # 테이블별 레코드 수 확인
            count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = count_result.scalar()
            print(f"   - {table_name}: {count}건")


async def create_sample_data():
    """샘플 데이터 생성"""
    from app.services.user_service import UserService
    from app.db.database import AsyncSessionLocal
    from app.schemas.user import UserCreate
    from app.models.user import UserRole, UserStatus
    
    print("샘플 데이터 생성 중...")
    
    async with AsyncSessionLocal() as db:
        user_service = UserService(db)
        
        # 관리자 계정 존재 확인
        admin_user = await user_service.get_user_by_email("admin@example.com")
        if not admin_user:
            admin_data = UserCreate(
                name="시스템 관리자",
                email="admin@example.com",
                password="Admin123!",
                role=UserRole.SUPER_ADMIN,
                company="BrandFlow",
                contact="010-1234-5678"
            )
            admin_user = await user_service.create_user(admin_data)
            print(f"관리자 계정 생성: {admin_user.email}")
        else:
            print("관리자 계정이 이미 존재합니다")
        
        await db.commit()


if __name__ == "__main__":
    asyncio.run(setup_database())