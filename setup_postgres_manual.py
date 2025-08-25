#!/usr/bin/env python3
"""
Manual PostgreSQL setup with detailed instructions
"""

import os
import sys

def print_setup_instructions():
    """Print detailed manual setup instructions"""
    print("=" * 60)
    print("BrandFlow PostgreSQL 수동 설정 가이드")
    print("=" * 60)
    print()
    
    print("1단계: PostgreSQL 접속 테스트")
    print("-" * 30)
    print("다음 중 하나의 방법으로 PostgreSQL에 접속해보세요:")
    print()
    print("방법 1: pgAdmin 사용")
    print("  - pgAdmin 4를 실행하세요")
    print("  - 새 서버 연결: localhost:5432")
    print("  - 사용자: postgres")
    print("  - 비밀번호를 입력하세요")
    print()
    
    print("방법 2: 명령줄 사용 (관리자 권한 필요)")
    print('  - 관리자 권한으로 명령 프롬프트 열기')
    print('  - cd "C:\\Program Files\\PostgreSQL\\17\\bin"')
    print('  - psql -U postgres -d postgres')
    print('  - 비밀번호 입력')
    print()
    
    print("2단계: 데이터베이스 및 사용자 생성")
    print("-" * 30)
    print("PostgreSQL에 접속한 후 다음 SQL을 실행하세요:")
    print()
    print("-- brandflow_user 생성")
    print("CREATE USER brandflow_user WITH PASSWORD 'brandflow_password_2024';")
    print()
    print("-- brandflow 데이터베이스 생성")
    print("CREATE DATABASE brandflow OWNER brandflow_user ENCODING 'UTF8';")
    print()
    print("-- 권한 부여")
    print("GRANT ALL PRIVILEGES ON DATABASE brandflow TO brandflow_user;")
    print()
    print("-- 연결 테스트")
    print("\\c brandflow brandflow_user")
    print("SELECT 'Connection successful!' as status;")
    print()
    
    print("3단계: 연결 확인")
    print("-" * 30)
    print("다음 정보로 연결이 가능한지 확인하세요:")
    print("  호스트: localhost")
    print("  포트: 5432")
    print("  데이터베이스: brandflow")
    print("  사용자: brandflow_user")
    print("  비밀번호: brandflow_password_2024")
    print()
    
    print("4단계: BrandFlow 애플리케이션 설정")
    print("-" * 30)
    print("PostgreSQL 설정이 완료되면:")
    print("  1. python migrate_to_postgresql.py (데이터 마이그레이션)")
    print("  2. copy .env.postgresql .env (환경 설정 변경)")
    print("  3. FastAPI 서버 재시작")
    print()
    
    print("troubleshooting")
    print("-" * 30)
    print("연결 문제 해결:")
    print("1. PostgreSQL 서비스 상태 확인")
    print("   - services.msc 실행")
    print("   - postgresql-x64-17 서비스가 실행 중인지 확인")
    print()
    print("2. 비밀번호 재설정 (관리자 권한)")
    print("   - net user postgres <새비밀번호>")
    print("   - 또는 PostgreSQL 재설치")
    print()
    print("3. 방화벽 확인")
    print("   - 포트 5432가 열려있는지 확인")
    print()
    print("4. Docker 대안 사용")
    print("   - Docker Desktop 설치")
    print("   - docker run --name brandflow-postgres -e POSTGRES_USER=brandflow_user -e POSTGRES_PASSWORD=brandflow_password_2024 -e POSTGRES_DB=brandflow -p 5432:5432 -d postgres:15-alpine")
    print()
    
    print("=" * 60)

def create_sql_setup_file():
    """Create SQL setup file for manual execution"""
    sql_content = """-- BrandFlow PostgreSQL Setup
-- 이 파일을 PostgreSQL에서 직접 실행하세요

-- 1. brandflow_user 생성
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_catalog.pg_roles 
        WHERE rolname = 'brandflow_user'
    ) THEN
        CREATE USER brandflow_user WITH PASSWORD 'brandflow_password_2024';
        RAISE NOTICE 'brandflow_user created';
    ELSE
        RAISE NOTICE 'brandflow_user already exists';
    END IF;
END $$;

-- 2. brandflow 데이터베이스 생성
SELECT 'CREATE DATABASE brandflow OWNER brandflow_user ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'brandflow')\\gexec

-- 3. 권한 부여
GRANT ALL PRIVILEGES ON DATABASE brandflow TO brandflow_user;

-- 4. 연결 테스트용 (brandflow 데이터베이스에서 실행)
\\c brandflow brandflow_user

-- 5. 성공 메시지
SELECT 'BrandFlow PostgreSQL setup completed successfully!' as status;

-- 연결 정보 확인
SELECT current_database() as database, current_user as user;
"""
    
    with open('brandflow_setup.sql', 'w', encoding='utf-8') as f:
        f.write(sql_content)
    
    print("✅ SQL 설정 파일이 생성되었습니다: brandflow_setup.sql")
    print()
    print("사용 방법:")
    print('1. pgAdmin에서 파일 열기 후 실행')
    print('2. 또는 psql -U postgres -d postgres -f brandflow_setup.sql')

def main():
    print_setup_instructions()
    print()
    create_sql_setup_file()
    
    print()
    print("다음 단계를 완료한 후 'python test_postgres_connection.py'를 실행하여 연결을 확인하세요.")

if __name__ == "__main__":
    main()