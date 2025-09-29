#!/usr/bin/env python3
"""
posts 테이블에 assigned_user_id 컬럼을 추가하는 마이그레이션 스크립트
"""

import asyncio
from sqlalchemy import text
from app.db.database import async_engine


async def add_post_assignment_column():
    """posts 테이블에 assigned_user_id 컬럼 추가"""

    try:
        async with async_engine.begin() as conn:
            # 컬럼 존재 여부 확인
            result = await conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'posts' AND column_name = 'assigned_user_id'
            """))
            column_exists = result.fetchone() is not None

            if not column_exists:
                print("[INFO] posts 테이블에 assigned_user_id 컬럼을 추가합니다...")

                # 컬럼 추가
                await conn.execute(text("""
                    ALTER TABLE posts
                    ADD COLUMN assigned_user_id INTEGER REFERENCES users(id)
                """))

                print("[SUCCESS] assigned_user_id 컬럼이 성공적으로 추가되었습니다.")

                # 기존 포스트들의 담당자를 캠페인 생성자로 설정
                print("[INFO] 기존 포스트들의 담당자를 캠페인 생성자로 설정합니다...")

                result = await conn.execute(text("""
                    UPDATE posts
                    SET assigned_user_id = campaigns.creator_id
                    FROM campaigns
                    WHERE posts.campaign_id = campaigns.id
                    AND posts.assigned_user_id IS NULL
                """))

                updated_count = result.rowcount
                print(f"[SUCCESS] {updated_count}개 포스트의 담당자가 설정되었습니다.")

                # 결과 확인
                result = await conn.execute(text("""
                    SELECT
                        COUNT(*) as total_posts,
                        COUNT(assigned_user_id) as assigned_posts,
                        COUNT(CASE WHEN assigned_user_id IS NULL THEN 1 END) as unassigned_posts
                    FROM posts
                """))
                stats = result.fetchone()
                print(f"[INFO] 마이그레이션 결과: 전체 {stats.total_posts}개, 담당자 설정 {stats.assigned_posts}개, 미설정 {stats.unassigned_posts}개")

            else:
                print("[INFO] assigned_user_id 컬럼이 이미 존재합니다.")

    except Exception as e:
        print(f"[ERROR] 마이그레이션 중 오류 발생: {e}")
        raise


async def main():
    """메인 실행 함수"""
    print("[START] Post 담당자 필드 마이그레이션을 시작합니다...")
    await add_post_assignment_column()
    print("[COMPLETE] 마이그레이션이 완료되었습니다.")


if __name__ == "__main__":
    asyncio.run(main())