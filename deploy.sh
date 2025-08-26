#!/bin/bash

# BrandFlow FastAPI 배포 스크립트
# Railway와 다른 플랫폼에 대한 자동화된 배포

set -e  # 에러 발생 시 스크립트 중단

echo "🚀 BrandFlow FastAPI 배포 시작..."

# 환경 변수 확인
check_env_vars() {
    echo "📋 환경 변수 확인 중..."
    
    if [ -z "$RAILWAY_TOKEN" ]; then
        echo "⚠️  RAILWAY_TOKEN이 설정되지 않았습니다."
        echo "   Railway CLI로 로그인하거나 토큰을 설정해주세요."
        echo "   railway login 또는 export RAILWAY_TOKEN=your_token"
    fi
    
    if [ -z "$DATABASE_URL" ]; then
        echo "ℹ️  DATABASE_URL이 설정되지 않았습니다. SQLite를 사용합니다."
    fi
    
    echo "✅ 환경 변수 확인 완료"
}

# 의존성 설치 및 테스트
setup_and_test() {
    echo "📦 의존성 설치 중..."
    
    # 가상환경이 있으면 활성화
    if [ -d "venv" ]; then
        source venv/bin/activate
        echo "✅ 가상환경 활성화"
    elif [ -d ".venv" ]; then
        source .venv/bin/activate
        echo "✅ 가상환경 활성화"
    fi
    
    # 의존성 설치
    pip install -r requirements.txt
    echo "✅ 의존성 설치 완료"
    
    # 기본 코드 검증
    echo "🔍 기본 코드 검증 중..."
    python -c "import app.main; print('✅ 코드 import 성공')"
    
    # 테스트 실행 (있는 경우)
    if [ -d "tests" ] && [ -n "$(ls -A tests)" ]; then
        echo "🧪 테스트 실행 중..."
        python -m pytest tests/ -v || echo "⚠️  일부 테스트 실패, 계속 진행..."
    else
        echo "ℹ️  테스트 파일이 없습니다. 건너뛰기..."
    fi
    
    echo "✅ 설정 및 테스트 완료"
}

# Railway 배포
deploy_railway() {
    echo "🚂 Railway 배포 중..."
    
    # Railway CLI 확인
    if ! command -v railway &> /dev/null; then
        echo "❌ Railway CLI가 설치되지 않았습니다."
        echo "   설치 방법: npm install -g @railway/cli"
        echo "   또는: curl -fsSL https://railway.app/install.sh | sh"
        return 1
    fi
    
    # Railway 로그인 확인
    if ! railway whoami &> /dev/null; then
        echo "❌ Railway에 로그인되지 않았습니다."
        echo "   railway login 명령으로 로그인해주세요."
        return 1
    fi
    
    # 배포 실행
    echo "🔄 Railway 배포 시작..."
    railway up
    
    if [ $? -eq 0 ]; then
        echo "✅ Railway 배포 성공!"
        
        # 배포된 URL 가져오기
        APP_URL=$(railway status --json | jq -r '.deployments[0].url' 2>/dev/null || echo "")
        if [ -n "$APP_URL" ] && [ "$APP_URL" != "null" ]; then
            echo "🌐 배포된 URL: $APP_URL"
            
            # 헬스 체크
            echo "🔍 헬스 체크 중..."
            sleep 30  # 서버 시작 대기
            
            if curl -f "$APP_URL/health" &> /dev/null; then
                echo "✅ 헬스 체크 성공!"
            else
                echo "⚠️  헬스 체크 실패. 수동으로 확인해주세요."
            fi
            
            # 모니터링 체크
            echo "📊 모니터링 시스템 체크 중..."
            if curl -f "$APP_URL/api/monitoring/health" &> /dev/null; then
                echo "✅ 모니터링 시스템 정상!"
            else
                echo "⚠️  모니터링 시스템 체크 실패"
            fi
        fi
    else
        echo "❌ Railway 배포 실패!"
        return 1
    fi
}

# Docker 배포 (선택사항)
deploy_docker() {
    echo "🐳 Docker 배포 준비 중..."
    
    if [ ! -f "Dockerfile" ]; then
        echo "ℹ️  Dockerfile이 없습니다. 건너뛰기..."
        return 0
    fi
    
    # Docker 이미지 빌드
    echo "🔨 Docker 이미지 빌드 중..."
    docker build -t brandflow-api .
    
    if [ $? -eq 0 ]; then
        echo "✅ Docker 이미지 빌드 성공!"
        echo "   로컬 실행: docker run -p 8000:8000 brandflow-api"
    else
        echo "❌ Docker 이미지 빌드 실패!"
    fi
}

# 배포 후 정리
cleanup() {
    echo "🧹 정리 작업 중..."
    
    # 임시 파일 정리
    find . -name "*.pyc" -delete
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    echo "✅ 정리 완료"
}

# 메인 실행
main() {
    echo "=================================================================="
    echo "🎯 BrandFlow FastAPI 자동 배포 스크립트"
    echo "=================================================================="
    
    # 함수들 실행
    check_env_vars
    setup_and_test
    
    # 배포 플랫폼 선택
    case "${1:-railway}" in
        "railway")
            deploy_railway
            ;;
        "docker")
            deploy_docker
            ;;
        "both")
            deploy_railway
            deploy_docker
            ;;
        *)
            echo "❌ 알 수 없는 배포 타입: $1"
            echo "   사용법: ./deploy.sh [railway|docker|both]"
            exit 1
            ;;
    esac
    
    cleanup
    
    echo "=================================================================="
    echo "🎉 배포 스크립트 완료!"
    echo "=================================================================="
}

# 스크립트 실행
main "$@"