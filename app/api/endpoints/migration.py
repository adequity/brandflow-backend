from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_db
from app.core.security import get_current_user
from app.models.user import UserRole
import os
import logging

# Optional alembic import with graceful fallback
try:
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    ALEMBIC_AVAILABLE = True
except ImportError:
    ALEMBIC_AVAILABLE = False
    logging.warning("Alembic not available - migration features will be limited")

router = APIRouter()

@router.post("/run-migration")
async def run_migration(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    데이터베이스 마이그레이션을 실행합니다.
    슈퍼 어드민만 실행 가능합니다.
    """
    # 권한 체크 - 슈퍼 어드민만 허용
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="마이그레이션 실행 권한이 없습니다. 슈퍼 어드민만 가능합니다."
        )

    # Alembic 사용 가능 여부 확인
    if not ALEMBIC_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="마이그레이션 도구(Alembic)가 설치되지 않았습니다. 관리자에게 문의하세요."
        )

    try:
        # Alembic 설정 파일 경로 확인
        alembic_ini_path = "alembic.ini"
        if not os.path.exists(alembic_ini_path):
            raise HTTPException(
                status_code=404,
                detail="Alembic 설정 파일(alembic.ini)을 찾을 수 없습니다."
            )

        alembic_cfg = Config(alembic_ini_path)

        # 현재 리비전 확인
        from sqlalchemy import text
        from app.db.database import engine

        current_version = None
        async with engine.begin() as conn:
            try:
                # 현재 마이그레이션 상태 확인
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                current_version = result.scalar()
                logging.info(f"현재 마이그레이션 버전: {current_version}")
            except Exception as e:
                logging.warning(f"마이그레이션 버전 확인 실패: {str(e)}")

        # 마이그레이션 실행
        command.upgrade(alembic_cfg, "head")

        return {
            "message": "마이그레이션이 성공적으로 완료되었습니다",
            "previous_version": current_version,
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"마이그레이션 실행 중 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"마이그레이션 실행 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/migration-status")
async def get_migration_status(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    현재 마이그레이션 상태를 확인합니다.
    """
    try:
        from sqlalchemy import text

        current_version = None
        alembic_available = ALEMBIC_AVAILABLE

        # Alembic이 있을 때만 현재 마이그레이션 버전 확인
        if ALEMBIC_AVAILABLE:
            try:
                result = await db.execute(text("SELECT version_num FROM alembic_version"))
                current_version = result.scalar()
            except Exception as e:
                logging.warning(f"마이그레이션 버전 확인 실패: {str(e)}")
                current_version = "unknown"

        # 테이블 존재 여부 확인
        tables_check = await db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'posts'
            AND column_name IN ('start_datetime', 'due_datetime')
        """))

        new_columns = [row[0] for row in tables_check.fetchall()]

        return {
            "alembic_available": alembic_available,
            "current_version": current_version,
            "new_datetime_columns_exist": len(new_columns) > 0,
            "existing_columns": new_columns,
            "migration_needed": len(new_columns) == 0
        }

    except Exception as e:
        logging.error(f"마이그레이션 상태 확인 중 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"마이그레이션 상태 확인 중 오류: {str(e)}"
        )