#!/usr/bin/env python3
"""
Railway PostgreSQL 데이터베이스에 강제 마이그레이션 실행
client_user_id 컬럼 추가와 데이터 마이그레이션을 강제로 실행합니다.
"""

import asyncio
import os
from sqlalchemy import text
from app.db.database import async_engine

async def force_migration():
    """강제로 마이그레이션 실행"""
    try:
        async with async_engine.begin() as conn:
            print("Starting forced database migration...")
            
            # 1. client_user_id 컬럼 존재 여부 확인
            print("1. Checking if client_user_id column exists...")
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'campaigns' AND column_name = 'client_user_id'
            """))
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("   Adding client_user_id column...")
                # 컬럼 추가
                await conn.execute(text("""
                    ALTER TABLE campaigns 
                    ADD COLUMN client_user_id INTEGER REFERENCES users(id)
                """))
                print("   ✓ client_user_id column added successfully")
            else:
                print("   ✓ client_user_id column already exists")
                
            # 2. 기존 데이터 마이그레이션
            print("2. Migrating existing client_company data to client_user_id...")
            
            # client_company에서 (ID: user_id) 패턴 추출하여 client_user_id 업데이트
            result = await conn.execute(text("""
                UPDATE campaigns 
                SET client_user_id = CAST(
                    SUBSTRING(client_company FROM '\\(ID: (\\d+)\\)') AS INTEGER
                )
                WHERE client_company LIKE '%(ID: %)' 
                AND (client_user_id IS NULL OR client_user_id != CAST(
                    SUBSTRING(client_company FROM '\\(ID: (\\d+)\\)') AS INTEGER
                ))
            """))
            
            updated_count = result.rowcount
            print(f"   ✓ Successfully migrated {updated_count} campaigns with client_user_id")
            
            # 3. 마이그레이션 결과 확인
            print("3. Verifying migration results...")
            check_result = await conn.execute(text("""
                SELECT COUNT(*) as total_campaigns,
                       COUNT(client_user_id) as with_client_user_id,
                       COUNT(CASE WHEN client_company LIKE '%(ID: %)' THEN 1 END) as with_id_pattern
                FROM campaigns
            """))
            stats = check_result.fetchone()
            print(f"   Total campaigns: {stats[0]}")
            print(f"   With client_user_id: {stats[1]}")
            print(f"   With ID pattern: {stats[2]}")
            
            print("\n✓ Database migration completed successfully")
            
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        print(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(force_migration())