import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import List, Tuple
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import and_, func, or_

from app.db.database import engine
from app.models.user import User, UserRole
from app.models.post import Post
from app.models.campaign import Campaign
from app.models.user_telegram_setting import UserTelegramSetting, TelegramNotificationLog
from app.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)

# 데이터베이스 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TelegramScheduler:
    """텔레그램 알림 스케줄러"""

    def __init__(self):
        self.running = False
        self.check_interval = 900  # 15분마다 체크 (더 자주 확인)

    async def start(self):
        """스케줄러 시작"""
        if self.running:
            logger.warning("텔레그램 스케줄러가 이미 실행 중입니다")
            return

        self.running = True
        logger.info("텔레그램 알림 스케줄러 시작")

        while self.running:
            try:
                await self.check_and_send_notifications()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"스케줄러 오류: {str(e)}")
                await asyncio.sleep(60)  # 오류 시 1분 후 재시도

    def stop(self):
        """스케줄러 중지"""
        self.running = False
        logger.info("텔레그램 알림 스케줄러 중지")

    async def check_and_send_notifications(self):
        """마감일 임박 알림 확인 및 전송"""
        db = SessionLocal()

        try:
            logger.info(f"[TELEGRAM] 마감일 임박 알림 확인 시작 - {datetime.utcnow()}")

            # 클라이언트 역할을 제외한 모든 사용자들의 활성화된 텔레그램 설정 조회
            telegram_users = db.query(UserTelegramSetting).join(User).filter(
                and_(
                    User.role != UserRole.CLIENT,  # 클라이언트 역할 제외
                    UserTelegramSetting.is_enabled == True,
                    User.is_active == True
                )
            ).all()

            if not telegram_users:
                logger.info("[TELEGRAM] 알림을 받을 사용자가 없습니다")
                return

            logger.info(f"[TELEGRAM] 알림 대상 사용자 수: {len(telegram_users)}")

            notifications_sent = 0

            for telegram_setting in telegram_users:
                user = telegram_setting.user

                # 해당 사용자가 담당하는 posts 조회 (사용자가 생성한 캠페인의 posts)
                user_posts = await self.get_user_posts_with_upcoming_deadlines(
                    db, user.id, telegram_setting.days_before_due
                )

                for post_info in user_posts:
                    post, campaign, days_left = post_info

                    # 이미 알림을 보낸 적이 있는지 확인
                    existing_log = db.query(TelegramNotificationLog).filter(
                        and_(
                            TelegramNotificationLog.user_id == user.id,
                            TelegramNotificationLog.post_id == post.id,
                            TelegramNotificationLog.notification_type == "due_date_reminder",
                            TelegramNotificationLog.is_sent == True,
                            func.date(TelegramNotificationLog.created_at) == func.date(datetime.utcnow())
                        )
                    ).first()

                    if existing_log:
                        logger.debug(f"이미 알림 전송됨: user_id={user.id}, post_id={post.id}")
                        continue

                    # 알림 시간 확인 (현재 시간이 설정된 알림 시간과 비슷한지)
                    current_time = datetime.now().strftime("%H:%M")
                    if not self.is_notification_time(telegram_setting.notification_time):
                        logger.debug(f"[TELEGRAM] 알림 시간이 아님 - 설정: {telegram_setting.notification_time}, 현재: {current_time}")
                        continue

                    logger.info(f"[TELEGRAM] 알림 시간 조건 만족 - 사용자: {user.name}, 설정시간: {telegram_setting.notification_time}, 현재시간: {current_time}")

                    # 텔레그램 알림 전송
                    await self.send_deadline_notification(
                        db, user, post, campaign, days_left, telegram_setting
                    )
                    notifications_sent += 1

            logger.info(f"[TELEGRAM] 마감일 임박 알림 {notifications_sent}개 전송 완료 - {datetime.utcnow()}")

        except Exception as e:
            logger.error(f"알림 확인 중 오류: {str(e)}")
        finally:
            db.close()

    async def get_user_posts_with_upcoming_deadlines(
        self, db: Session, user_id: int, days_before: int
    ) -> List[Tuple[Post, Campaign, float]]:
        """사용자의 마감일 임박 posts 조회 (DateTime 기반)"""

        try:
            # 현재 일시 (정확한 시간 고려)
            now = datetime.now()
            logger.info(f"[TELEGRAM] 마감일 체크 기준 시간: {now}")

            # 사용자가 생성한 캠페인의 posts 조회 (due_datetime 우선, due_date 대체)
            posts_with_deadlines = db.query(Post, Campaign).join(Campaign).filter(
                and_(
                    Campaign.creator_id == user_id,
                    # due_datetime 또는 due_date가 있는 경우
                    or_(Post.due_datetime.isnot(None), Post.due_date.isnot(None)),
                    Post.is_active == True
                )
            ).all()

            logger.info(f"[TELEGRAM] 사용자 {user_id}의 마감일 있는 posts: {len(posts_with_deadlines)}개")

            upcoming_posts = []

            for post, campaign in posts_with_deadlines:
                try:
                    due_datetime = None

                    # due_datetime 우선 사용, 없으면 due_date 사용
                    if post.due_datetime:
                        due_datetime = post.due_datetime
                        logger.debug(f"[TELEGRAM] Post {post.id}: due_datetime 사용 - {due_datetime}")
                    elif post.due_date:
                        # due_date를 due_datetime으로 변환 (기본 시간: 18:00)
                        try:
                            due_date_only = datetime.strptime(post.due_date, "%Y-%m-%d").date()
                            due_datetime = datetime.combine(due_date_only, datetime.strptime("18:00", "%H:%M").time())
                            logger.debug(f"[TELEGRAM] Post {post.id}: due_date를 due_datetime으로 변환 - {due_datetime}")
                        except ValueError:
                            logger.warning(f"[TELEGRAM] 잘못된 날짜 형식: post_id={post.id}, due_date={post.due_date}")
                            continue

                    if due_datetime:
                        # 현재 시간부터 마감일까지의 시간 차이 계산
                        time_diff = due_datetime - now
                        hours_left = time_diff.total_seconds() / 3600  # 시간 단위
                        days_left = hours_left / 24  # 일 단위

                        logger.debug(f"[TELEGRAM] Post {post.id}: 마감까지 {hours_left:.1f}시간 ({days_left:.1f}일)")

                        # 마감일이 설정된 일수 이내인 경우 (더 정확한 계산)
                        if -0.5 <= days_left <= days_before:  # 마감 후 12시간까지도 포함
                            upcoming_posts.append((post, campaign, days_left))
                            logger.info(f"[TELEGRAM] 알림 대상 추가: Post {post.id} ({post.title}) - {days_left:.1f}일 후 마감")

                except Exception as e:
                    logger.error(f"[TELEGRAM] Post {post.id} 처리 중 오류: {str(e)}")
                    continue

            logger.info(f"[TELEGRAM] 총 알림 대상 posts: {len(upcoming_posts)}개")
            return upcoming_posts

        except Exception as e:
            logger.error(f"마감일 임박 posts 조회 오류: {str(e)}")
            return []

    async def send_deadline_notification(
        self,
        db: Session,
        user: User,
        post: Post,
        campaign: Campaign,
        days_left: float,
        telegram_setting: UserTelegramSetting
    ):
        """마감일 알림 전송"""

        try:
            # 마감일 정보 준비 (due_datetime 우선, due_date 대체)
            due_info = ""
            if post.due_datetime:
                due_info = post.due_datetime.strftime("%Y-%m-%d %H:%M")
            elif post.due_date:
                due_info = f"{post.due_date} 18:00"  # 기본 마감시간

            # 알림 메시지 전송
            result = await telegram_service.send_campaign_deadline_reminder(
                chat_id=telegram_setting.telegram_chat_id,
                user_name=user.name,
                post_title=post.title,
                due_date=due_info,  # 시간까지 포함된 정보
                days_left=days_left,
                campaign_id=campaign.id,
                post_id=post.id
            )

            # 로그 저장
            log = TelegramNotificationLog(
                user_id=user.id,
                post_id=post.id,
                campaign_id=campaign.id,
                notification_type="due_date_reminder",
                message_content=f"마감일 {days_left:.1f}일 전 알림: {post.title} (마감: {due_info})",
                telegram_chat_id=telegram_setting.telegram_chat_id,
                is_sent=result.get("success", False),
                sent_at=datetime.utcnow() if result.get("success") else None,
                error_message=result.get("error") if not result.get("success") else None,
                telegram_message_id=str(result.get("message_id", "")) if result.get("success") else None
            )

            db.add(log)
            db.commit()

            if result.get("success"):
                logger.info(f"마감일 알림 전송 성공: user={user.name}, post={post.title}")

                # 마지막 알림 시간 업데이트
                telegram_setting.last_notification_at = datetime.utcnow()
                db.commit()
            else:
                logger.error(f"마감일 알림 전송 실패: user={user.name}, error={result.get('error')}")

        except Exception as e:
            logger.error(f"마감일 알림 전송 중 오류: {str(e)}")

    def is_notification_time(self, notification_time: str) -> bool:
        """현재 시간이 알림 시간인지 확인"""
        try:
            # 알림 시간 파싱 (HH:MM)
            hour, minute = map(int, notification_time.split(':'))
            target_time = time(hour, minute)

            # 현재 시간
            current_time = datetime.now().time()

            # ±2시간 범위 내에서 알림 시간으로 판단 (더 넓은 범위)
            target_minutes = hour * 60 + minute
            current_minutes = current_time.hour * 60 + current_time.minute

            return abs(current_minutes - target_minutes) <= 120

        except Exception as e:
            logger.error(f"알림 시간 확인 오류: {str(e)}")
            return False


# 전역 스케줄러 인스턴스
telegram_scheduler = TelegramScheduler()


async def start_telegram_scheduler():
    """텔레그램 스케줄러 시작"""
    await telegram_scheduler.start()


def stop_telegram_scheduler():
    """텔레그램 스케줄러 중지"""
    telegram_scheduler.stop()