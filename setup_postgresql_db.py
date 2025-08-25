#!/usr/bin/env python3
"""
PostgreSQL 데이터베이스 설정 스크립트
"""

import asyncio
import asyncpg
import sys


async def setup_database():
    """PostgreSQL 데이터베이스와 사용자 설정"""
    print("PostgreSQL 데이터베이스 설정 시작...")
    
    # PostgreSQL 기본 사용자로 연결 시도
    connection_strings = [
        "postgresql://postgres:@localhost:5432/postgres",
        "postgresql://postgres:postgres@localhost:5432/postgres",
        "postgresql://postgres:admin@localhost:5432/postgres",
    ]
    
    conn = None
    for conn_str in connection_strings:
        try:
            print(f"연결 시도: {conn_str.replace(':@', ':<no_password>@').replace(':postgres@', ':<password>@').replace(':admin@', ':<password>@')}")
            conn = await asyncpg.connect(conn_str)
            print("✅ PostgreSQL 연결 성공!")
            break
        except Exception as e:
            print(f"연결 실패: {e}")
            continue
    
    if not conn:
        print("❌ PostgreSQL에 연결할 수 없습니다.")
        print("\n해결 방법:")
        print("1. PostgreSQL 서비스가 실행 중인지 확인")
        print("2. postgres 사용자의 비밀번호 확인")
        print("3. pg_hba.conf 설정에서 로컬 연결 허용 확인")
        return False
    
    try:
        # brandflow_user 생성
        try:
            await conn.execute("""
                CREATE ROLE brandflow_user LOGIN PASSWORD 'brandflow_password_2024'
            """)
            print("✅ brandflow_user 사용자 생성됨")
        except asyncpg.DuplicateObjectError:
            print("ℹ️  brandflow_user 사용자가 이미 존재함")
        except Exception as e:
            print(f"⚠️  사용자 생성 중 오류: {e}")
        
        # brandflow 데이터베이스 생성
        try:
            await conn.execute("""
                CREATE DATABASE brandflow OWNER brandflow_user 
                ENCODING 'UTF8' LC_COLLATE='C' LC_CTYPE='C'
            """)
            print("✅ brandflow 데이터베이스 생성됨")
        except asyncpg.DuplicateDatabaseError:
            print("ℹ️  brandflow 데이터베이스가 이미 존재함")
        except Exception as e:
            print(f"⚠️  데이터베이스 생성 중 오류: {e}")
        
        # 권한 부여
        await conn.execute("GRANT ALL PRIVILEGES ON DATABASE brandflow TO brandflow_user")
        print("✅ 데이터베이스 권한 부여 완료")
        
        await conn.close()
        
        # brandflow 데이터베이스에 연결하여 추가 설정
        try:
            brandflow_conn = await asyncpg.connect(
                "postgresql://brandflow_user:brandflow_password_2024@localhost:5432/brandflow"
            )
            
            # 스키마 권한 설정
            await brandflow_conn.execute("""
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO brandflow_user
            """)
            await brandflow_conn.execute("""
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO brandflow_user
            """)
            print("✅ 스키마 권한 설정 완료")
            
            await brandflow_conn.close()
            
        except Exception as e:
            print(f"⚠️  스키마 권한 설정 중 오류 (무시 가능): {e}")
        
        print("\n🎉 PostgreSQL 데이터베이스 설정 완료!")
        print("연결 정보:")
        print("  호스트: localhost")
        print("  포트: 5432")
        print("  데이터베이스: brandflow")
        print("  사용자: brandflow_user")
        print("  비밀번호: brandflow_password_2024")
        print("\n연결 URL:")
        print("postgresql://brandflow_user:brandflow_password_2024@localhost:5432/brandflow")
        
        return True
        
    except Exception as e:
        print(f"❌ 데이터베이스 설정 실패: {e}")
        if conn:
            await conn.close()
        return False


async def test_connection():
    """brandflow 데이터베이스 연결 테스트"""
    print("\n🔧 연결 테스트 중...")
    
    try:
        conn = await asyncpg.connect(
            "postgresql://brandflow_user:brandflow_password_2024@localhost:5432/brandflow"
        )
        
        # 버전 확인
        version = await conn.fetchval("SELECT version()")
        print(f"✅ 연결 성공! PostgreSQL 버전: {version.split()[0]} {version.split()[1]}")
        
        # 테스트 테이블 생성 및 삭제
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100)
            )
        """)
        await conn.execute("INSERT INTO test_table (name) VALUES ('test')")
        
        count = await conn.fetchval("SELECT COUNT(*) FROM test_table")
        print(f"✅ 테이블 작업 테스트 성공 (레코드 수: {count})")
        
        await conn.execute("DROP TABLE test_table")
        print("✅ 테스트 테이블 정리 완료")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 연결 테스트 실패: {e}")
        return False


async def main():
    print("=== BrandFlow PostgreSQL 설정 ===")
    
    # 데이터베이스 설정
    setup_success = await setup_database()
    if not setup_success:
        return 1
    
    # 연결 테스트
    test_success = await test_connection()
    if not test_success:
        return 1
    
    print("\n✅ 모든 설정이 완료되었습니다!")
    print("\n다음 단계:")
    print("1. python migrate_to_postgresql.py (기존 SQLite 데이터가 있다면)")
    print("2. copy .env.postgresql .env")
    print("3. FastAPI 서버 재시작")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)