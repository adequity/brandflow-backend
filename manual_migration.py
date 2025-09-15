#!/usr/bin/env python3
"""
수동 마이그레이션 스크립트: campaigns 테이블에 start_date, end_date 컬럼 추가
"""
import asyncio
import asyncpg
import os
from datetime import datetime

# Railway 데이터베이스 연결 정보
DATABASE_URL = "postgresql://postgres:kAPUkGlWqoHwxIvtWaeukQuwcrZpSzuu@junction.proxy.rlwy.net:21652/railway"

async def check_columns_exist():
    """현재 campaigns 테이블의 컬럼 확인"""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # 테이블 구조 확인
        result = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'campaigns' 
            ORDER BY ordinal_position;
        """)
        
        print("현재 campaigns 테이블 구조:")
        for row in result:
            print(f"  {row['column_name']}: {row['data_type']} ({'NULL' if row['is_nullable'] == 'YES' else 'NOT NULL'})")
        
        # start_date, end_date 컬럼 존재 확인
        columns = [row['column_name'] for row in result]
        start_date_exists = 'start_date' in columns
        end_date_exists = 'end_date' in columns
        
        return start_date_exists, end_date_exists
        
    finally:
        await conn.close()

async def add_date_columns():
    """start_date, end_date 컬럼 추가"""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("start_date, end_date 컬럼 추가 중...")
        
        # start_date 컬럼 추가 (임시로 nullable로 추가)
        await conn.execute("""
            ALTER TABLE campaigns 
            ADD COLUMN IF NOT EXISTS start_date TIMESTAMP;
        """)
        
        # end_date 컬럼 추가 (임시로 nullable로 추가)
        await conn.execute("""
            ALTER TABLE campaigns 
            ADD COLUMN IF NOT EXISTS end_date TIMESTAMP;
        """)
        
        print("✅ 컬럼 추가 완료")
        
        # 기존 데이터에 기본값 설정 (현재 날짜)
        current_time = datetime.now()
        
        await conn.execute("""
            UPDATE campaigns 
            SET start_date = $1, end_date = $2 
            WHERE start_date IS NULL OR end_date IS NULL;
        """, current_time, current_time)
        
        print("✅ 기존 데이터에 기본값 설정 완료")
        
        # 컬럼을 NOT NULL로 변경
        await conn.execute("""
            ALTER TABLE campaigns 
            ALTER COLUMN start_date SET NOT NULL;
        """)
        
        await conn.execute("""
            ALTER TABLE campaigns 
            ALTER COLUMN end_date SET NOT NULL;
        """)
        
        print("✅ 컬럼을 NOT NULL로 설정 완료")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        raise
    finally:
        await conn.close()

async def main():
    """메인 실행 함수"""
    print("=== campaigns 테이블 마이그레이션 시작 ===")
    
    # 1. 현재 상태 확인
    start_exists, end_exists = await check_columns_exist()
    
    if start_exists and end_exists:
        print("✅ start_date, end_date 컬럼이 이미 존재합니다.")
        return
    
    # 2. 컬럼 추가
    if not start_exists or not end_exists:
        await add_date_columns()
    
    # 3. 최종 확인
    print("\n=== 마이그레이션 완료 후 테이블 구조 ===")
    await check_columns_exist()
    
    print("\n✅ 마이그레이션 완료!")

if __name__ == "__main__":
    asyncio.run(main())