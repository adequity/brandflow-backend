#!/usr/bin/env python3
"""
Railway PostgreSQL 데이터베이스 스키마 상태 확인 스크립트
client_user_id 컬럼 존재 여부와 마이그레이션 상태를 확인합니다.
"""

import asyncio
import os
from sqlalchemy import text
from app.db.database import async_engine

async def check_schema_status():
    """데이터베이스 스키마 상태 확인"""
    try:
        async with async_engine.begin() as conn:
            print("🔍 PostgreSQL 스키마 상태 확인 중...")
            print(f"Database URL: {os.getenv('DATABASE_URL', 'Not set')}")
            
            # 1. campaigns 테이블의 컬럼 목록 확인
            print("\n📋 campaigns 테이블 컬럼 목록:")
            columns_result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'campaigns' 
                ORDER BY ordinal_position
            """))
            columns = columns_result.fetchall()
            
            for col in columns:
                print(f"  - {col.column_name}: {col.data_type} ({'NULL' if col.is_nullable == 'YES' else 'NOT NULL'})")
            
            # 2. client_user_id 컬럼 존재 여부 확인
            print("\n🔍 client_user_id 컬럼 존재 여부:")
            client_user_id_exists = any(col.column_name == 'client_user_id' for col in columns)
            print(f"  client_user_id 컬럼: {'✅ 존재함' if client_user_id_exists else '❌ 존재하지 않음'}")
            
            # 3. 외래키 관계 확인
            print("\n🔗 campaigns 테이블 외래키 관계:")
            fk_result = await conn.execute(text("""
                SELECT 
                    tc.constraint_name, 
                    kcu.column_name, 
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name 
                FROM information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' 
                    AND tc.table_name='campaigns'
            """))
            foreign_keys = fk_result.fetchall()
            
            for fk in foreign_keys:
                print(f"  - {fk.column_name} → {fk.foreign_table_name}.{fk.foreign_column_name}")
            
            # 4. campaigns 데이터 샘플 확인 (client_company 패턴과 client_user_id 값)
            print("\n📊 campaigns 테이블 데이터 샘플 (처음 5개):")
            if client_user_id_exists:
                data_result = await conn.execute(text("""
                    SELECT id, name, client_company, client_user_id, creator_id 
                    FROM campaigns 
                    ORDER BY id 
                    LIMIT 5
                """))
            else:
                data_result = await conn.execute(text("""
                    SELECT id, name, client_company, creator_id 
                    FROM campaigns 
                    ORDER BY id 
                    LIMIT 5
                """))
            
            campaigns = data_result.fetchall()
            for campaign in campaigns:
                if client_user_id_exists:
                    print(f"  ID: {campaign.id}, Name: {campaign.name}")
                    print(f"    client_company: {campaign.client_company}")
                    print(f"    client_user_id: {campaign.client_user_id}")
                    print(f"    creator_id: {campaign.creator_id}")
                else:
                    print(f"  ID: {campaign.id}, Name: {campaign.name}")
                    print(f"    client_company: {campaign.client_company}")
                    print(f"    creator_id: {campaign.creator_id}")
                print()
            
            # 5. 마이그레이션이 필요한 데이터 개수 확인
            print("📈 마이그레이션 통계:")
            stats_result = await conn.execute(text("""
                SELECT 
                    COUNT(*) as total_campaigns,
                    COUNT(CASE WHEN client_company LIKE '%(ID: %)' THEN 1 END) as with_id_pattern
                FROM campaigns
            """))
            stats = stats_result.fetchone()
            print(f"  전체 캠페인: {stats.total_campaigns}개")
            print(f"  ID 패턴이 있는 캠페인: {stats.with_id_pattern}개")
            
            if client_user_id_exists:
                client_user_id_stats = await conn.execute(text("""
                    SELECT COUNT(client_user_id) as with_client_user_id
                    FROM campaigns
                    WHERE client_user_id IS NOT NULL
                """))
                client_stats = client_user_id_stats.fetchone()
                print(f"  client_user_id가 설정된 캠페인: {client_stats.with_client_user_id}개")
            
            print("\n✅ 스키마 상태 확인 완료")
            
    except Exception as e:
        print(f"❌ 스키마 확인 중 오류 발생: {e}")
        print(f"오류 타입: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(check_schema_status())