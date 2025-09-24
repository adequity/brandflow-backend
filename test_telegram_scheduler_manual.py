#!/usr/bin/env python3
"""
텔레그램 스케줄러 수동 테스트 스크립트
실제 알림 시간에 텔레그램 알림이 제대로 작동하는지 확인
"""
import sys
import os
import asyncio
from datetime import datetime, timedelta

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.telegram_scheduler import telegram_scheduler
from app.db.database import SessionLocal
from app.models.user_telegram_setting import UserTelegramSetting, TelegramNotificationLog
from app.models.user import User
from app.models.post import Post
from app.models.campaign import Campaign
from sqlalchemy import and_, func

async def test_telegram_scheduler():
    """텔레그램 스케줄러 테스트"""

    print("=" * 60)
    print("[TELEGRAM] 텔레그램 스케줄러 테스트 시작")
    print("=" * 60)

    db = SessionLocal()

    try:
        # 1. 텔레그램 설정이 있는 사용자 확인
        print("\n[USER] 텔레그램 설정 사용자 확인:")
        telegram_users = db.query(UserTelegramSetting).join(User).filter(
            and_(
                UserTelegramSetting.is_enabled == True,
                User.is_active == True
            )
        ).all()

        if not telegram_users:
            print("[ERROR] 텔레그램 설정이 활성화된 사용자가 없습니다.")
            return

        for setting in telegram_users:
            user = setting.user
            print(f"  [OK] {user.name} ({user.role}) - 채팅ID: {setting.telegram_chat_id}")
            print(f"     알림시간: {setting.notification_time}, {setting.days_before_due}일 전 알림")

        # 2. 마감일이 임박한 포스트 확인
        print(f"\n[POST] 마감일 임박 포스트 확인 (현재 시간: {datetime.now()})")

        now = datetime.now()
        for setting in telegram_users:
            user = setting.user

            # 사용자가 생성한 캠페인의 포스트들 조회
            user_posts = db.query(Post).join(Campaign).filter(
                and_(
                    Campaign.creator_id == user.id,
                    Post.status.in_(["진행중", "대기중"]),
                    Post.due_date.isnot(None)
                )
            ).all()

            print(f"\n  [USER] {user.name}의 포스트:")
            if not user_posts:
                print(f"    [EMPTY] 마감일이 있는 포스트가 없습니다.")
                continue

            for post in user_posts:
                try:
                    # due_date를 datetime으로 파싱
                    from app.utils.date_utils import parse_due_datetime
                    due_datetime = parse_due_datetime(post.due_date)

                    if due_datetime:
                        days_diff = (due_datetime - now).days
                        print(f"    [POST] {post.title[:30]}... - 마감: {post.due_date} ({days_diff}일 후)")

                        # 알림 대상인지 확인
                        if days_diff <= setting.days_before_due and days_diff >= 0:
                            print(f"      [NOTIFY] 알림 대상! ({setting.days_before_due}일 전 설정)")
                    else:
                        print(f"    [POST] {post.title[:30]}... - 마감: {post.due_date} (파싱 실패)")

                except Exception as e:
                    print(f"    [WARN] 포스트 처리 오류: {str(e)}")

        # 3. 실제 스케줄러 실행 (강제 모드)
        print(f"\n[SCHEDULER] 스케줄러 강제 실행 테스트:")
        print("   시간 제약 없이 알림 대상 포스트에 대해 텔레그램 알림 발송...")

        # 원래 is_notification_time 함수 백업
        original_is_notification_time = telegram_scheduler.is_notification_time

        # 강제 실행: 모든 시간대에서 알림 허용
        telegram_scheduler.is_notification_time = lambda time_str: True

        try:
            # 알림 체크 및 전송 실행
            await telegram_scheduler.check_and_send_notifications()
            print("   [OK] 스케줄러 실행 완료")
        except Exception as e:
            print(f"   [ERROR] 스케줄러 실행 오류: {str(e)}")
        finally:
            # 원래 함수 복원
            telegram_scheduler.is_notification_time = original_is_notification_time

        # 4. 최근 알림 로그 확인
        print(f"\n[LOG] 최근 알림 로그 (최근 24시간):")
        recent_logs = db.query(TelegramNotificationLog).filter(
            TelegramNotificationLog.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).order_by(TelegramNotificationLog.created_at.desc()).limit(10).all()

        if not recent_logs:
            print("   [EMPTY] 최근 24시간 내 알림 로그가 없습니다.")
        else:
            for log in recent_logs:
                status = "[OK]" if log.is_sent else "[FAIL]"
                print(f"   {status} - {log.notification_type} - {log.created_at}")
                if log.error_message:
                    print(f"     오류: {log.error_message}")
                if log.message_content:
                    print(f"     내용: {log.message_content[:50]}...")

    except Exception as e:
        print(f"[ERROR] 테스트 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()

    print("\n" + "=" * 60)
    print("[COMPLETE] 텔레그램 스케줄러 테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_telegram_scheduler())