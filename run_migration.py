#!/usr/bin/env python3
"""
Railway 환경에서 Alembic 마이그레이션 실행
"""
import os
import sys
import subprocess
from alembic.config import Config
from alembic import command

def run_migration():
    """Alembic 마이그레이션 실행"""
    try:
        print("Starting Alembic migration...")

        # Alembic 설정 파일 경로
        alembic_cfg = Config("alembic.ini")

        # 현재 revision 확인
        print("Checking current revision...")
        command.current(alembic_cfg, verbose=True)

        # 마이그레이션 실행
        print("Running migration to head...")
        command.upgrade(alembic_cfg, "head")

        print("Migration completed successfully!")
        return True

    except Exception as e:
        print(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)