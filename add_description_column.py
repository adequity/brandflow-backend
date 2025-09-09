#!/usr/bin/env python3
"""
데이터베이스에 campaigns.description 컬럼을 추가하는 마이그레이션 스크립트
"""

import asyncio
import logging
from sqlalchemy import text
from app.db.database import get_async_db, async_engine
from app.models.campaign import Campaign

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def add_description_column():
    """campaigns 테이블에 description 컬럼 추가"""
    
    try:
        # 데이터베이스 연결
        async with async_engine.begin() as conn:
            # PostgreSQL/SQLite 호환 방식으로 컬럼 추가
            try:
                # 먼저 컬럼이 이미 존재하는지 확인
                result = await conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'campaigns' AND column_name = 'description'
                """))
                
                existing_column = result.fetchone()
                
                if existing_column:
                    logger.info("description 컬럼이 이미 존재합니다.")
                    return
                    
            except Exception as e:
                # SQLite의 경우 information_schema가 없으므로 직접 시도
                logger.info(f"컬럼 존재 여부 확인 실패 (SQLite인 경우 정상): {e}")
            
            # description 컬럼 추가
            try:
                await conn.execute(text("""
                    ALTER TABLE campaigns 
                    ADD COLUMN description TEXT
                """))
                logger.info("✅ campaigns.description 컬럼이 성공적으로 추가되었습니다.")
                
            except Exception as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    logger.info("description 컬럼이 이미 존재합니다.")
                else:
                    raise e
                    
            # 기존 데이터에 대해 NULL 값을 빈 문자열로 업데이트 (선택적)
            await conn.execute(text("""
                UPDATE campaigns 
                SET description = '' 
                WHERE description IS NULL
            """))
            logger.info("✅ 기존 레코드의 description 값을 빈 문자열로 업데이트했습니다.")
            
    except Exception as e:
        logger.error(f"❌ 마이그레이션 실패: {e}")
        raise

async def main():
    """메인 실행 함수"""
    logger.info("=== campaigns.description 컬럼 추가 마이그레이션 시작 ===")
    
    try:
        await add_description_column()
        logger.info("=== 마이그레이션 완료 ===")
        
    except Exception as e:
        logger.error(f"=== 마이그레이션 실패: {e} ===")
        return False
        
    return True

if __name__ == "__main__":
    # 마이그레이션 실행
    success = asyncio.run(main())
    if success:
        print("✅ 마이그레이션이 성공적으로 완료되었습니다.")
    else:
        print("❌ 마이그레이션이 실패했습니다.")
        exit(1)