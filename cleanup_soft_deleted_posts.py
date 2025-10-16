"""
이미 Soft Delete된 posts를 DB에서 완전히 삭제하는 스크립트
"""
import asyncio
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_db, async_engine
from app.models.post import Post
from app.models.order_request import OrderRequest
from app.models.user_telegram_setting import TelegramNotificationLog


async def cleanup_soft_deleted_posts():
    """is_active = False인 posts와 관련 데이터를 DB에서 완전히 삭제"""

    async with AsyncSession(async_engine) as db:
        try:
            # 1. Soft Delete된 posts 조회
            query = select(Post).where(Post.is_active == False)
            result = await db.execute(query)
            soft_deleted_posts = result.scalars().all()

            if not soft_deleted_posts:
                print("[OK] Soft Delete된 posts가 없습니다.")
                return

            post_ids = [post.id for post in soft_deleted_posts]
            print(f"[INFO] 삭제 대상 posts: {len(post_ids)}개")
            print(f"[INFO] Post IDs: {post_ids}")

            # 2. 관련 telegram_notification_logs 삭제
            telegram_stmt = sql_delete(TelegramNotificationLog).where(
                TelegramNotificationLog.post_id.in_(post_ids)
            )
            telegram_result = await db.execute(telegram_stmt)
            print(f"[INFO] - TelegramNotificationLog 삭제: {telegram_result.rowcount}개")

            # 3. 관련 order_requests 삭제
            order_stmt = sql_delete(OrderRequest).where(
                OrderRequest.post_id.in_(post_ids)
            )
            order_result = await db.execute(order_stmt)
            print(f"[INFO] - OrderRequest 삭제: {order_result.rowcount}개")

            # 4. Posts 삭제
            posts_stmt = sql_delete(Post).where(Post.id.in_(post_ids))
            posts_result = await db.execute(posts_stmt)
            print(f"[INFO] - Posts 삭제: {posts_result.rowcount}개")

            await db.commit()
            print(f"[SUCCESS] Soft Delete된 posts {len(post_ids)}개를 DB에서 완전히 삭제했습니다.")

        except Exception as e:
            await db.rollback()
            print(f"[ERROR] 삭제 중 오류 발생: {e}")
            raise


if __name__ == "__main__":
    print("[CLEANUP] Soft Delete된 posts 정리 시작...")
    asyncio.run(cleanup_soft_deleted_posts())
    print("[CLEANUP] 정리 완료!")
