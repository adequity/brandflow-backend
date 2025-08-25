#!/usr/bin/env python3
"""
PostgreSQL 연결 테스트 스크립트
"""

import asyncio
import asyncpg
import psycopg2
import sys

async def test_asyncpg_connection():
    """asyncpg 연결 테스트"""
    print("1. asyncpg 연결 테스트...")
    try:
        conn = await asyncpg.connect(
            "postgresql://brandflow_user:brandflow_password_2024@localhost:5432/brandflow"
        )
        
        # 버전 확인
        version = await conn.fetchval("SELECT version()")
        print(f"   ✅ asyncpg 연결 성공!")
        print(f"   PostgreSQL 버전: {version.split()[1]}")
        
        # 테스트 쿼리
        result = await conn.fetchval("SELECT 'Hello from PostgreSQL!' as message")
        print(f"   테스트 쿼리 결과: {result}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ asyncpg 연결 실패: {e}")
        return False

def test_psycopg2_connection():
    """psycopg2 연결 테스트"""
    print("\n2. psycopg2 연결 테스트...")
    try:
        conn = psycopg2.connect(
            host='localhost',
            port='5432',
            database='brandflow',
            user='brandflow_user',
            password='brandflow_password_2024'
        )
        
        cursor = conn.cursor()
        
        # 버전 확인
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"   ✅ psycopg2 연결 성공!")
        print(f"   PostgreSQL 버전: {version.split()[1]}")
        
        # 테스트 쿼리
        cursor.execute("SELECT 'Hello from PostgreSQL!' as message")
        result = cursor.fetchone()[0]
        print(f"   테스트 쿼리 결과: {result}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ psycopg2 연결 실패: {e}")
        return False

async def test_sqlalchemy_connection():
    """SQLAlchemy 연결 테스트"""
    print("\n3. SQLAlchemy 연결 테스트...")
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        
        engine = create_async_engine(
            "postgresql+asyncpg://brandflow_user:brandflow_password_2024@localhost:5432/brandflow"
        )
        
        async with engine.begin() as conn:
            result = await conn.execute("SELECT version()")
            version = result.fetchone()[0]
            print(f"   ✅ SQLAlchemy 연결 성공!")
            print(f"   PostgreSQL 버전: {version.split()[1]}")
        
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f"   ❌ SQLAlchemy 연결 실패: {e}")
        return False

async def main():
    print("=" * 50)
    print("BrandFlow PostgreSQL 연결 테스트")
    print("=" * 50)
    
    # 연결 테스트
    asyncpg_ok = await test_asyncpg_connection()
    psycopg2_ok = test_psycopg2_connection()
    sqlalchemy_ok = await test_sqlalchemy_connection()
    
    print("\n" + "=" * 50)
    print("테스트 결과 요약")
    print("=" * 50)
    print(f"asyncpg:     {'✅ 성공' if asyncpg_ok else '❌ 실패'}")
    print(f"psycopg2:    {'✅ 성공' if psycopg2_ok else '❌ 실패'}")
    print(f"SQLAlchemy:  {'✅ 성공' if sqlalchemy_ok else '❌ 실패'}")
    
    if all([asyncpg_ok, psycopg2_ok, sqlalchemy_ok]):
        print("\n🎉 모든 연결 테스트 성공!")
        print("\n다음 단계:")
        print("1. python migrate_to_postgresql.py (데이터 마이그레이션)")
        print("2. copy .env.postgresql .env (환경 설정 변경)")  
        print("3. FastAPI 서버 재시작")
        return 0
    else:
        print("\n❌ 일부 연결 테스트 실패")
        print("\n해결 방법:")
        print("1. PostgreSQL 서비스가 실행 중인지 확인")
        print("2. brandflow_user와 brandflow 데이터베이스가 생성되었는지 확인")
        print("3. python setup_postgres_manual.py 가이드 참조")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)