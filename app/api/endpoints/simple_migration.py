from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from alembic import command
from alembic.config import Config
import logging

router = APIRouter()

@router.get("/run-now")
async def run_migration_now():
    """
    즉시 마이그레이션을 실행합니다.
    보안을 위해 단순한 GET 요청으로 제한합니다.
    """
    try:
        from app.db.database import engine

        logging.info("마이그레이션 시작...")

        # 현재 상태 확인
        async with engine.begin() as conn:
            try:
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                current_version = result.scalar()
                logging.info(f"현재 버전: {current_version}")
            except Exception as e:
                logging.warning(f"alembic_version 테이블 없음: {e}")
                current_version = None

        # 마이그레이션 실행
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

        # 결과 확인
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            new_version = result.scalar()

            # 새 컬럼 확인
            check_columns = await conn.execute(text("""
                SELECT column_name, table_name
                FROM information_schema.columns
                WHERE table_name IN ('posts', 'campaigns')
                AND column_name IN ('start_datetime', 'due_datetime', 'invoice_due_date', 'payment_due_date', 'project_due_date')
                ORDER BY table_name, column_name
            """))

            new_columns = [f"{row[1]}.{row[0]}" for row in check_columns.fetchall()]

        return {
            "success": True,
            "message": "마이그레이션 성공적으로 완료!",
            "previous_version": current_version,
            "current_version": new_version,
            "new_columns": new_columns,
            "timestamp": "2025-09-17"
        }

    except Exception as e:
        logging.error(f"마이그레이션 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"마이그레이션 실패: {str(e)}"
        )

@router.get("/status")
async def check_status():
    """마이그레이션 상태 확인"""
    try:
        from app.db.database import engine

        async with engine.begin() as conn:
            # 현재 버전 확인
            try:
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                current_version = result.scalar()
            except:
                current_version = None

            # 새 컬럼 존재 여부 확인
            check_columns = await conn.execute(text("""
                SELECT column_name, table_name
                FROM information_schema.columns
                WHERE table_name IN ('posts', 'campaigns')
                AND column_name IN ('start_datetime', 'due_datetime', 'invoice_due_date', 'payment_due_date', 'project_due_date')
            """))

            existing_columns = [f"{row[1]}.{row[0]}" for row in check_columns.fetchall()]
            migration_needed = len(existing_columns) < 5

        return {
            "current_version": current_version,
            "existing_columns": existing_columns,
            "migration_needed": migration_needed,
            "expected_columns": [
                "posts.start_datetime",
                "posts.due_datetime",
                "campaigns.invoice_due_date",
                "campaigns.payment_due_date",
                "campaigns.project_due_date"
            ]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"상태 확인 실패: {str(e)}"
        )