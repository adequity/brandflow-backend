#!/usr/bin/env python3
"""
PostgreSQL 데이터베이스 생성 스크립트
다양한 인증 방법을 시도합니다.
"""

import asyncio
import asyncpg
import sys
import getpass


async def try_connection_methods():
    """여러 인증 방법으로 PostgreSQL 연결 시도"""
    
    # 일반적인 연결 방법들
    connection_attempts = [
        # 비밀번호 없음 (trust 인증)
        "postgresql://postgres@localhost:5432/postgres",
        
        # 일반적인 기본 비밀번호들
        "postgresql://postgres:postgres@localhost:5432/postgres",
        "postgresql://postgres:admin@localhost:5432/postgres", 
        "postgresql://postgres:password@localhost:5432/postgres",
        "postgresql://postgres:123456@localhost:5432/postgres",
        
        # Windows 기본값들
        "postgresql://postgres:root@localhost:5432/postgres",
        "postgresql://postgres:sa@localhost:5432/postgres",
    ]
    
    print("PostgreSQL 연결 시도 중...")
    
    for i, conn_str in enumerate(connection_attempts, 1):
        try:
            # 비밀번호 표시용 URL
            display_url = conn_str.replace(":@", ":<no_password>@")
            if ":postgres@" not in conn_str and ":@" not in conn_str:
                parts = conn_str.split(":")
                if len(parts) >= 3:
                    password = parts[2].split("@")[0]
                    display_url = conn_str.replace(f":{password}@", ":<password>@")
            
            print(f"  시도 {i}: {display_url}")
            
            conn = await asyncpg.connect(conn_str)
            print(f"  ✓ 연결 성공!")
            
            # 데이터베이스 설정
            await setup_database(conn)
            await conn.close()
            return True
            
        except Exception as e:
            print(f"  ✗ 실패: {e}")
            continue
    
    print("\n모든 자동 연결 시도가 실패했습니다.")
    
    # 수동 비밀번호 입력 시도
    try:
        password = getpass.getpass("PostgreSQL postgres 사용자 비밀번호를 입력하세요: ")
        conn_str = f"postgresql://postgres:{password}@localhost:5432/postgres"
        
        print("수동 입력된 비밀번호로 연결 시도...")
        conn = await asyncpg.connect(conn_str)
        print("✓ 연결 성공!")
        
        await setup_database(conn)
        await conn.close()
        return True
        
    except Exception as e:
        print(f"✗ 수동 연결도 실패: {e}")
        return False


async def setup_database(conn):
    """데이터베이스와 사용자 생성"""
    print("\n데이터베이스 설정 중...")
    
    try:
        # brandflow_user 생성 (이미 존재하면 무시)
        try:
            await conn.execute("""
                CREATE USER brandflow_user WITH PASSWORD 'brandflow_password_2024'
            """)
            print("  ✓ brandflow_user 사용자 생성")
        except asyncpg.DuplicateObjectError:
            print("  ℹ brandflow_user가 이미 존재합니다")
        except Exception as e:
            print(f"  ! 사용자 생성 중 오류: {e}")
        
        # brandflow 데이터베이스 생성 (이미 존재하면 무시)
        try:
            await conn.execute("""
                CREATE DATABASE brandflow OWNER brandflow_user 
                ENCODING 'UTF8' LC_COLLATE='C' LC_CTYPE='C'
            """)
            print("  ✓ brandflow 데이터베이스 생성")
        except asyncpg.DuplicateDatabaseError:
            print("  ℹ brandflow 데이터베이스가 이미 존재합니다")
        except Exception as e:
            print(f"  ! 데이터베이스 생성 중 오류: {e}")
        
        # 권한 부여
        try:
            await conn.execute("GRANT ALL PRIVILEGES ON DATABASE brandflow TO brandflow_user")
            print("  ✓ 권한 부여 완료")
        except Exception as e:
            print(f"  ! 권한 부여 중 오류: {e}")
    
    except Exception as e:
        print(f"데이터베이스 설정 실패: {e}")
        raise


async def test_brandflow_connection():
    """brandflow 데이터베이스 연결 테스트"""
    print("\nbrandflow 데이터베이스 연결 테스트...")
    
    try:
        conn = await asyncpg.connect(
            "postgresql://brandflow_user:brandflow_password_2024@localhost:5432/brandflow"
        )
        
        # 테스트 쿼리
        version = await conn.fetchval("SELECT version()")
        print(f"  ✓ 연결 성공! PostgreSQL 버전: {version.split()[1]}")
        
        # 테스트 테이블 생성/삭제
        await conn.execute("CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY, name VARCHAR(100))")
        await conn.execute("INSERT INTO test_table (name) VALUES ('test')")
        count = await conn.fetchval("SELECT COUNT(*) FROM test_table")
        await conn.execute("DROP TABLE test_table")
        
        print(f"  ✓ 테이블 작업 테스트 성공 (레코드: {count}개)")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"  ✗ brandflow 데이터베이스 연결 실패: {e}")
        return False


async def main():
    print("=== BrandFlow PostgreSQL 데이터베이스 설정 ===\n")
    
    # PostgreSQL 연결 및 설정
    if not await try_connection_methods():
        print("\n❌ PostgreSQL 연결에 실패했습니다.")
        print("\n해결 방법:")
        print("1. PostgreSQL 서비스가 실행 중인지 확인")
        print("2. postgres 사용자의 비밀번호 확인")
        print("3. pg_hba.conf에서 로컬 연결이 허용되는지 확인")
        return 1
    
    # brandflow 데이터베이스 연결 테스트
    if await test_brandflow_connection():
        print("\n🎉 PostgreSQL 데이터베이스 설정이 완료되었습니다!")
        print("\n연결 정보:")
        print("  - 호스트: localhost")
        print("  - 포트: 5432") 
        print("  - 데이터베이스: brandflow")
        print("  - 사용자: brandflow_user")
        print("  - 비밀번호: brandflow_password_2024")
        print("\n다음 단계:")
        print("1. python migrate_to_postgresql.py (데이터 마이그레이션)")
        print("2. copy .env.postgresql .env (환경 설정 변경)")
        print("3. FastAPI 서버 재시작")
        return 0
    else:
        print("\n❌ brandflow 데이터베이스 설정에 문제가 있습니다.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)