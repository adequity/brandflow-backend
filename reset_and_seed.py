#!/usr/bin/env python3
"""
Database Reset and Seed Script
데이터베이스 리셋 및 시드 데이터 생성 스크립트
"""

import asyncio
import os
from pathlib import Path

from app.db.database import create_tables, AsyncSessionLocal
from app.db.init_data import init_database_data


async def reset_database():
    """Railway PostgreSQL 데이터베이스 초기화"""
    
    print("Railway PostgreSQL 데이터베이스 사용 중...")
    print("Note: PostgreSQL 데이터는 직접 삭제되지 않습니다. 테이블만 재생성합니다.")
    
    # 테이블 재생성
    print("데이터베이스 테이블 재생성...")
    await create_tables()
    print("테이블 생성 완료")


async def seed_database():
    """시드 데이터 생성"""
    print("\n시드 데이터 생성 시작...")
    
    async with AsyncSessionLocal() as session:
        await init_database_data(session)
    
    print("시드 데이터 생성 완료")


async def main():
    """메인 함수"""
    print("=== 데이터베이스 리셋 및 시드 데이터 생성 ===")
    
    try:
        # 1. 데이터베이스 리셋
        await reset_database()
        
        # 2. 시드 데이터 생성
        await seed_database()
        
        print("\n" + "="*50)
        print("데이터베이스 리셋 및 시드 데이터 생성 완료!")
        print("서버를 재시작하여 변경사항을 적용하세요.")
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())