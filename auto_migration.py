#!/usr/bin/env python3
"""
자동 마이그레이션: 앱 시작 시 DB 스키마 업데이트
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, MetaData, inspect
from app.core.config import settings
from app.models.base import Base
from app.models import campaign  # 모든 모델 import

logger = logging.getLogger(__name__)

async def check_and_update_schema():
    """DB 스키마 확인 및 업데이트"""
    try:
        # 비동기 엔진 생성
        engine = create_async_engine(settings.get_database_url)
        
        async with engine.begin() as conn:
            # 현재 campaigns 테이블 컬럼 확인
            result = await conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns 
                WHERE table_name = 'campaigns'
            """))
            
            existing_columns = {row[0] for row in result.fetchall()}
            logger.info(f"기존 campaigns 컬럼: {existing_columns}")
            
            # start_date, end_date 컬럼 확인 및 추가
            if 'start_date' not in existing_columns:
                logger.info("start_date 컬럼 추가 중...")
                await conn.execute(text("""
                    ALTER TABLE campaigns 
                    ADD COLUMN start_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                """))
                logger.info("✅ start_date 컬럼 추가 완료")
            
            if 'end_date' not in existing_columns:
                logger.info("end_date 컬럼 추가 중...")
                await conn.execute(text("""
                    ALTER TABLE campaigns 
                    ADD COLUMN end_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                """))
                logger.info("✅ end_date 컬럼 추가 완료")
            
            # 기본값 제거 (모델에서 nullable=False로 관리)
            if 'start_date' not in existing_columns or 'end_date' not in existing_columns:
                await conn.execute(text("""
                    ALTER TABLE campaigns 
                    ALTER COLUMN start_date DROP DEFAULT
                """))
                await conn.execute(text("""
                    ALTER TABLE campaigns 
                    ALTER COLUMN end_date DROP DEFAULT
                """))
                logger.info("✅ 기본값 제거 완료")
        
        await engine.dispose()
        logger.info("✅ 스키마 업데이트 완료")
        return True
        
    except Exception as e:
        logger.error(f"❌ 스키마 업데이트 실패: {e}")
        return False

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    
    # 마이그레이션 실행
    asyncio.run(check_and_update_schema())