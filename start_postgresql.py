#!/usr/bin/env python3
"""
PostgreSQL 시작 및 설정 스크립트

Docker 없이 로컬에서 PostgreSQL을 시작하는 대안 방법들을 제공합니다.
"""

import os
import subprocess
import sys
import time
import psutil


def check_docker_available():
    """Docker가 사용 가능한지 확인"""
    try:
        result = subprocess.run(['docker', '--version'], 
                              capture_output=True, text=True, check=True)
        print(f"[OK] Docker 사용 가능: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[ERROR] Docker를 찾을 수 없습니다.")
        return False


def check_postgresql_running():
    """PostgreSQL이 이미 실행 중인지 확인"""
    for proc in psutil.process_iter(['pid', 'name', 'connections']):
        if 'postgres' in proc.info['name'].lower():
            for conn in proc.info['connections'] or []:
                if conn.laddr.port == 5432:
                    print(f"✅ PostgreSQL이 이미 실행 중입니다 (PID: {proc.info['pid']})")
                    return True
    return False


def start_with_docker():
    """Docker Compose를 사용하여 PostgreSQL 시작"""
    if not os.path.exists('docker-compose.yml'):
        print("❌ docker-compose.yml 파일을 찾을 수 없습니다.")
        return False
    
    try:
        print("🐳 Docker Compose로 PostgreSQL 시작 중...")
        
        # PostgreSQL만 시작
        result = subprocess.run(['docker-compose', 'up', '-d', 'postgres'], 
                              check=True, capture_output=True, text=True)
        
        print("📊 PostgreSQL 컨테이너 상태 확인 중...")
        time.sleep(5)  # 시작 시간 대기
        
        # 헬스체크 대기
        for i in range(30):  # 최대 30초 대기
            result = subprocess.run(['docker-compose', 'ps', 'postgres'], 
                                  capture_output=True, text=True)
            if 'healthy' in result.stdout or '(healthy)' in result.stdout:
                print("✅ PostgreSQL이 성공적으로 시작되었습니다!")
                return True
            elif i < 29:
                print(f"⏳ PostgreSQL 시작 대기 중... ({i+1}/30)")
                time.sleep(1)
        
        print("⚠️  PostgreSQL이 시작되었지만 헬스체크가 완료되지 않았습니다.")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker Compose 실행 실패: {e}")
        print(f"오류 출력: {e.stderr}")
        return False


def show_connection_info():
    """연결 정보 표시"""
    print("\n" + "="*50)
    print("📋 PostgreSQL 연결 정보:")
    print("="*50)
    print("호스트: localhost")
    print("포트: 5432")
    print("데이터베이스: brandflow")
    print("사용자명: brandflow_user")
    print("비밀번호: brandflow_password_2024")
    print("\n연결 URL:")
    print("postgresql://brandflow_user:brandflow_password_2024@localhost:5432/brandflow")
    print("="*50)


def show_next_steps():
    """다음 단계 안내"""
    print("\n🚀 다음 단계:")
    print("1. PostgreSQL이 실행되면 마이그레이션을 실행하세요:")
    print("   python migrate_to_postgresql.py")
    print("\n2. 마이그레이션 완료 후 환경 설정을 변경하세요:")
    print("   copy .env.postgresql .env")
    print("\n3. FastAPI 서버를 재시작하세요:")
    print("   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001")


def show_alternatives():
    """대안 방법들 안내"""
    print("\n💡 대안 방법들:")
    print("="*50)
    
    print("\n1. 로컬 PostgreSQL 설치:")
    print("   - Windows: https://www.postgresql.org/download/windows/")
    print("   - 설치 후 pgAdmin을 사용하여 데이터베이스 생성")
    print("   - 사용자: brandflow_user, 데이터베이스: brandflow")
    
    print("\n2. Cloud PostgreSQL 사용:")
    print("   - Heroku Postgres (무료 tier)")
    print("   - AWS RDS (프리 티어)")
    print("   - Google Cloud SQL")
    print("   - Railway, PlanetScale 등")
    
    print("\n3. SQLite 계속 사용:")
    print("   - 현재 SQLite 설정을 유지")
    print("   - 개발 단계에서는 충분히 사용 가능")


def main():
    print("[DB] BrandFlow PostgreSQL 설정")
    print("="*50)
    
    # PostgreSQL이 이미 실행 중인지 확인
    if check_postgresql_running():
        show_connection_info()
        print("\n✅ PostgreSQL이 이미 실행 중입니다. 마이그레이션을 진행할 수 있습니다.")
        show_next_steps()
        return 0
    
    # Docker 사용 시도
    if check_docker_available():
        if start_with_docker():
            show_connection_info()
            show_next_steps()
            return 0
        else:
            print("\n❌ Docker로 PostgreSQL 시작에 실패했습니다.")
    
    # 대안 방법들 안내
    show_alternatives()
    
    print("\n📝 참고:")
    print("PostgreSQL을 다른 방법으로 설치한 후에는")
    print(".env.postgresql 파일의 연결 정보를 수정해주세요.")
    
    return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)