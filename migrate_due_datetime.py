#!/usr/bin/env python3
"""
posts.due_date를 due_datetime으로 마이그레이션하는 스크립트

기존: due_date = "2025-09-25" (문자열)
변경: due_datetime = "2025-09-25 18:00:00" (DateTime)
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import get_async_db
from app.models.post import Post


async def migrate_due_datetime():
    """due_date를 due_datetime으로 마이그레이션"""

    print("🔄 due_datetime 마이그레이션 시작...")

    # 데이터베이스 세션 생성
    async for db in get_async_db():
        try:
            # 1단계: due_datetime 컬럼이 존재하는지 확인
            print("📋 1단계: due_datetime 컬럼 존재 여부 확인...")

            # 컬럼 추가 (이미 있으면 무시됨)
            await db.execute(text("""
                ALTER TABLE posts
                ADD COLUMN IF NOT EXISTS due_datetime TIMESTAMP;
            """))

            await db.execute(text("""
                ALTER TABLE posts
                ADD COLUMN IF NOT EXISTS start_datetime TIMESTAMP;
            """))

            await db.commit()
            print("✅ due_datetime, start_datetime 컬럼 준비 완료")

            # 2단계: 기존 due_date 데이터 확인
            print("📋 2단계: 기존 due_date 데이터 확인...")

            result = await db.execute(text("""
                SELECT id, due_date, start_date, due_datetime, start_datetime
                FROM posts
                WHERE due_date IS NOT NULL
                AND due_date != ''
                LIMIT 10;
            """))

            posts_sample = result.fetchall()
            print(f"📊 due_date가 있는 posts 샘플: {len(posts_sample)}개")

            for post in posts_sample:
                print(f"  - ID: {post.id}, due_date: {post.due_date}, due_datetime: {post.due_datetime}")

            # 3단계: due_date → due_datetime 변환
            print("🔄 3단계: due_date → due_datetime 변환...")

            # 기본 마감시간: 오후 6시 (18:00)
            default_due_time = "18:00:00"
            default_start_time = "09:00:00"

            # due_date → due_datetime 변환 (due_datetime이 NULL인 경우만)
            due_update_result = await db.execute(text(f"""
                UPDATE posts
                SET due_datetime = (due_date || ' {default_due_time}')::timestamp
                WHERE due_date IS NOT NULL
                AND due_date != ''
                AND due_date ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$'
                AND due_datetime IS NULL;
            """))

            # start_date → start_datetime 변환 (start_datetime이 NULL인 경우만)
            start_update_result = await db.execute(text(f"""
                UPDATE posts
                SET start_datetime = (start_date || ' {default_start_time}')::timestamp
                WHERE start_date IS NOT NULL
                AND start_date != ''
                AND start_date ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$'
                AND start_datetime IS NULL;
            """))

            await db.commit()

            print(f"✅ due_datetime 변환 완료: {due_update_result.rowcount}개 행 업데이트")
            print(f"✅ start_datetime 변환 완료: {start_update_result.rowcount}개 행 업데이트")

            # 4단계: 변환 결과 확인
            print("📋 4단계: 변환 결과 확인...")

            result = await db.execute(text("""
                SELECT id, due_date, due_datetime, start_date, start_datetime
                FROM posts
                WHERE due_datetime IS NOT NULL
                LIMIT 5;
            """))

            converted_posts = result.fetchall()
            print(f"📊 변환된 posts 확인: {len(converted_posts)}개")

            for post in converted_posts:
                print(f"  - ID: {post.id}")
                print(f"    due_date: {post.due_date} → due_datetime: {post.due_datetime}")
                print(f"    start_date: {post.start_date} → start_datetime: {post.start_datetime}")

            # 5단계: 통계 출력
            print("📊 5단계: 마이그레이션 통계...")

            stats_result = await db.execute(text("""
                SELECT
                    COUNT(*) as total_posts,
                    COUNT(due_date) as posts_with_due_date,
                    COUNT(due_datetime) as posts_with_due_datetime,
                    COUNT(start_date) as posts_with_start_date,
                    COUNT(start_datetime) as posts_with_start_datetime
                FROM posts;
            """))

            stats = stats_result.fetchone()
            print(f"  📈 전체 posts: {stats.total_posts}")
            print(f"  📅 due_date 보유: {stats.posts_with_due_date}")
            print(f"  🕒 due_datetime 보유: {stats.posts_with_due_datetime}")
            print(f"  📅 start_date 보유: {stats.posts_with_start_date}")
            print(f"  🕒 start_datetime 보유: {stats.posts_with_start_datetime}")

            print("🎉 due_datetime 마이그레이션 완료!")

        except Exception as e:
            print(f"❌ 마이그레이션 중 오류: {e}")
            await db.rollback()
            raise
        finally:
            await db.close()
            break


if __name__ == "__main__":
    print("🚀 BrandFlow due_datetime 마이그레이션 시작")
    print("=" * 50)

    try:
        asyncio.run(migrate_due_datetime())
        print("=" * 50)
        print("✅ 마이그레이션 성공적으로 완료!")
    except Exception as e:
        print("=" * 50)
        print(f"❌ 마이그레이션 실패: {e}")
        sys.exit(1)