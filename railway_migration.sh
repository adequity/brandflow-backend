#!/bin/bash
# Railway에서 실행할 마이그레이션 스크립트

echo "🚀 Railway 마이그레이션 시작..."
echo "현재 디렉토리: $(pwd)"
echo "Python 버전: $(python --version)"

# 패키지 확인
echo "📦 필요한 패키지 확인..."
pip list | grep -E "(alembic|sqlalchemy|asyncpg)"

# 마이그레이션 실행
echo "🔧 마이그레이션 실행..."
python run_migration.py

echo "✅ 마이그레이션 스크립트 완료!"