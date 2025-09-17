#!/usr/bin/env python3
"""
Railway에서 직접 실행할 수 있는 마이그레이션 스크립트
"""
import os
import sys
import asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from app.db.database import engine

async def run_migration():
    """마이그레이션을 실행합니다."""
    print("🔧 데이터베이스 마이그레이션을 시작합니다...")

    try:
        # 현재 마이그레이션 상태 확인
        async with engine.begin() as conn:
            try:
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                current_version = result.scalar()
                print(f"📊 현재 마이그레이션 버전: {current_version}")
            except Exception as e:
                print(f"⚠️ alembic_version 테이블이 없습니다: {e}")
                current_version = None

        # Alembic 설정
        alembic_cfg = Config("alembic.ini")

        # 마이그레이션 실행
        print("🚀 마이그레이션을 실행합니다...")
        command.upgrade(alembic_cfg, "head")

        # 마이그레이션 후 상태 확인
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            new_version = result.scalar()
            print(f"✅ 마이그레이션 완료! 새 버전: {new_version}")

            # 새로 추가된 컬럼 확인
            check_columns = await conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name IN ('posts', 'campaigns')
                AND column_name IN ('start_datetime', 'due_datetime', 'invoice_due_date', 'payment_due_date', 'project_due_date')
                ORDER BY table_name, column_name
            """))

            new_columns = check_columns.fetchall()
            if new_columns:
                print("🎯 새로 추가된 컬럼들:")
                for col_name, col_type in new_columns:
                    print(f"   - {col_name}: {col_type}")
            else:
                print("⚠️ 새 컬럼이 확인되지 않습니다.")

        print("🎉 마이그레이션이 성공적으로 완료되었습니다!")
        return True

    except Exception as e:
        print(f"❌ 마이그레이션 실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🗄️ BrandFlow 데이터베이스 마이그레이션")
    print("=" * 50)

    # 환경 변수 확인
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL 환경 변수가 설정되지 않았습니다.")
        sys.exit(1)

    print(f"🔗 데이터베이스: {db_url.split('@')[1] if '@' in db_url else 'localhost'}")

    # 마이그레이션 실행
    success = asyncio.run(run_migration())

    if success:
        print("\n🎊 마이그레이션 완료! 일정 관리 기능이 활성화되었습니다.")
        sys.exit(0)
    else:
        print("\n💥 마이그레이션 실패!")
        sys.exit(1)