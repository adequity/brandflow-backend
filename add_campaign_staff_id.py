#!/usr/bin/env python3
"""
캠페인 테이블에 staff_id 컬럼 추가 마이그레이션
담당자 설정을 위한 필드 추가
"""

import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import async_engine
from app.models.user import User
from app.models.campaign import Campaign

async def add_staff_id_column():
    """campaigns 테이블에 staff_id 컬럼 추가"""
    async with async_engine.begin() as conn:
        try:
            print("campaigns 테이블에 staff_id 컬럼 추가 중...")

            # staff_id 컬럼 추가
            await conn.execute(text("""
                ALTER TABLE campaigns
                ADD COLUMN IF NOT EXISTS staff_id INTEGER
                REFERENCES users(id);
            """))

            print("staff_id 컬럼 추가 완료")

            # 기존 캠페인들의 staff_id를 creator_id로 초기화 (임시)
            result = await conn.execute(text("""
                UPDATE campaigns
                SET staff_id = creator_id
                WHERE staff_id IS NULL;
            """))

            rows_updated = result.rowcount
            print(f"기존 캠페인 {rows_updated}개의 staff_id를 creator_id로 초기화 완료")

            # 결과 확인
            result = await conn.execute(text("""
                SELECT id, name, creator_id, staff_id
                FROM campaigns
                ORDER BY id
                LIMIT 10;
            """))
            campaigns = result.fetchall()

            print(f"\n마이그레이션 결과 확인 (첫 10개):")
            for campaign in campaigns:
                print(f"  캠페인 {campaign.id}: {campaign.name} - 생성자: {campaign.creator_id}, 담당자: {campaign.staff_id}")

            return True

        except SQLAlchemyError as e:
            print(f"데이터베이스 오류: {e}")
            return False
        except Exception as e:
            print(f"예상치 못한 오류: {e}")
            return False

async def main():
    """메인 실행 함수"""
    print("campaigns 테이블 staff_id 컬럼 추가 마이그레이션 시작")

    success = await add_staff_id_column()

    if success:
        print("\n마이그레이션이 성공적으로 완료되었습니다!")
        print("이제 캠페인에 담당 직원을 설정할 수 있습니다.")
    else:
        print("\n마이그레이션이 실패했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())