#!/usr/bin/env python3
"""
Debug script to check campaign dates and SQL extract behavior
"""
import asyncio
import asyncpg
import os
from datetime import datetime

async def debug_campaign_dates():
    """Debug campaign dates for user 3333 (staff_id = 5)"""

    # Railway database connection
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("DATABASE_URL not found")
        return

    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)

        print("=== 캠페인 날짜 디버깅 ===")
        print(f"현재 시간: {datetime.now()}")
        print()

        # Check campaigns for staff_id = 5 (user 3333)
        query = """
        SELECT
            id,
            name,
            start_date,
            end_date,
            staff_id,
            budget,
            EXTRACT(year FROM start_date) as start_year,
            EXTRACT(month FROM start_date) as start_month,
            DATE_PART('year', start_date) as date_part_year,
            DATE_PART('month', start_date) as date_part_month
        FROM campaigns
        WHERE staff_id = 5
        ORDER BY start_date;
        """

        rows = await conn.fetch(query)

        print(f"staff_id=5인 캠페인 총 {len(rows)}개:")
        for row in rows:
            print(f"  캠페인 {row['id']}: {row['name']}")
            print(f"    시작일: {row['start_date']} (타입: {type(row['start_date'])})")
            print(f"    종료일: {row['end_date']}")
            print(f"    예산: {row['budget']}")
            print(f"    EXTRACT(year): {row['start_year']} (타입: {type(row['start_year'])})")
            print(f"    EXTRACT(month): {row['start_month']} (타입: {type(row['start_month'])})")
            print(f"    DATE_PART(year): {row['date_part_year']}")
            print(f"    DATE_PART(month): {row['date_part_month']}")
            print()

        # Test the exact filtering query
        print("=== 9월 필터링 테스트 ===")
        filter_query = """
        SELECT
            id,
            name,
            start_date,
            EXTRACT(year FROM start_date) as extract_year,
            EXTRACT(month FROM start_date) as extract_month
        FROM campaigns
        WHERE staff_id = 5
            AND EXTRACT(year FROM start_date) = 2025
            AND EXTRACT(month FROM start_date) = 9;
        """

        filtered_rows = await conn.fetch(filter_query)
        print(f"2025년 9월 필터링 결과: {len(filtered_rows)}개 캠페인")
        for row in filtered_rows:
            print(f"  캠페인 {row['id']}: {row['name']}")
            print(f"    시작일: {row['start_date']}")
            print(f"    연도: {row['extract_year']}, 월: {row['extract_month']}")

        # Check data types
        print("\n=== 데이터 타입 확인 ===")
        type_query = """
        SELECT
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_name = 'campaigns'
            AND column_name IN ('start_date', 'end_date', 'staff_id');
        """

        type_rows = await conn.fetch(type_query)
        for row in type_rows:
            print(f"{row['column_name']}: {row['data_type']} (nullable: {row['is_nullable']})")

        await conn.close()

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    asyncio.run(debug_campaign_dates())