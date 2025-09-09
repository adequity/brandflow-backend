#!/usr/bin/env python3
"""
Railway 배포 환경에서 campaigns.description 컬럼을 추가하는 마이그레이션
"""

import os
import asyncio
import logging
import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_railway_database():
    """Railway PostgreSQL에 description 컬럼 추가"""
    
    # Railway PostgreSQL 연결 정보
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        logger.error("DATABASE_URL 환경변수가 설정되지 않았습니다.")
        return False
        
    try:
        # PostgreSQL 직접 연결
        conn = await asyncpg.connect(DATABASE_URL)
        
        try:
            # 컬럼 존재 여부 확인
            existing = await conn.fetchval("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'campaigns' AND column_name = 'description'
            """)
            
            if existing:
                logger.info("✅ description 컬럼이 이미 존재합니다.")
                return True
            
            # description 컬럼 추가
            await conn.execute("""
                ALTER TABLE campaigns 
                ADD COLUMN description TEXT
            """)
            logger.info("✅ campaigns.description 컬럼 추가 성공")
            
            # 기존 레코드 업데이트
            result = await conn.execute("""
                UPDATE campaigns 
                SET description = '' 
                WHERE description IS NULL
            """)
            logger.info(f"✅ 기존 레코드 업데이트 완료: {result}")
            
            return True
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"❌ Railway 마이그레이션 실패: {e}")
        return False

async def main():
    """메인 실행"""
    logger.info("=== Railway Database Migration 시작 ===")
    
    success = await migrate_railway_database()
    
    if success:
        logger.info("=== Railway 마이그레이션 완료 ===")
    else:
        logger.error("=== Railway 마이그레이션 실패 ===")
        
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)