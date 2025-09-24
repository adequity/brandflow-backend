#!/usr/bin/env python3
"""
텔레그램 스케줄러 시뮬레이션 테스트
실제 데이터베이스 없이 스케줄러 로직 검증
"""

import sys
import os
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.date_utils import parse_due_datetime, should_send_telegram_notification

@dataclass
class MockPost:
    """모의 Post 객체"""
    id: int
    title: str
    due_date: str
    is_active: bool = True

@dataclass
class MockCampaign:
    """모의 Campaign 객체"""
    id: int
    creator_id: int
    name: str

@dataclass
class MockUser:
    """모의 User 객체"""
    id: int
    name: str
    email: str

@dataclass
class MockTelegramSetting:
    """모의 TelegramSetting 객체"""
    user_id: int
    telegram_chat_id: str
    days_before_due: int
    notification_time: str
    is_enabled: bool = True

def simulate_get_user_posts_with_upcoming_deadlines(
    user_id: int,
    days_before: int,
    mock_posts: List[MockPost],
    mock_campaigns: List[MockCampaign]
) -> List[tuple]:
    """
    실제 get_user_posts_with_upcoming_deadlines 로직 시뮬레이션
    """
    now = datetime.now()
    print(f"[SIM] 마감일 체크 기준 시간: {now}")

    # 사용자가 생성한 캠페인 필터링
    user_campaigns = [c for c in mock_campaigns if c.creator_id == user_id]
    user_campaign_ids = [c.id for c in user_campaigns]

    # 해당 캠페인의 posts 필터링
    posts_with_deadlines = [
        (p, next(c for c in mock_campaigns if c.id == p.id))  # post와 campaign 매핑
        for p in mock_posts
        if p.due_date and p.due_date.strip() and p.is_active and p.id in user_campaign_ids
    ]

    print(f"[SIM] 사용자 {user_id}의 마감일 있는 posts: {len(posts_with_deadlines)}개")

    upcoming_posts = []

    for post, campaign in posts_with_deadlines:
        try:
            # date_utils의 parse_due_datetime 함수 사용
            due_datetime = parse_due_datetime(post.due_date, default_time="18:00")

            if not due_datetime:
                print(f"[SIM] 날짜 파싱 실패: post_id={post.id}, due_date={post.due_date}")
                continue

            print(f"[SIM] Post {post.id}: 파싱된 마감일시 - {due_datetime}")

            # should_send_telegram_notification 함수 사용하여 알림 여부 판단
            should_send, days_left = should_send_telegram_notification(
                due_datetime=due_datetime,
                days_before_setting=days_before,
                current_time=now,
                grace_period_hours=12.0  # 마감 후 12시간까지 유예
            )

            if should_send:
                upcoming_posts.append((post, campaign, days_left))
                print(f"[SIM] 알림 대상 추가: Post {post.id} ({post.title}) - {days_left:.1f}일 후 마감")

        except Exception as e:
            print(f"[SIM] Post {post.id} 처리 중 오류: {str(e)}")
            continue

    print(f"[SIM] 총 알림 대상 posts: {len(upcoming_posts)}개")
    return upcoming_posts

def simulate_is_notification_time(notification_time: str) -> bool:
    """알림 시간 확인 시뮬레이션"""
    try:
        # 알림 시간 파싱 (HH:MM)
        hour, minute = map(int, notification_time.split(':'))

        # 현재 시간
        current_time = datetime.now().time()

        # ±2시간 범위 내에서 알림 시간으로 판단
        target_minutes = hour * 60 + minute
        current_minutes = current_time.hour * 60 + current_time.minute

        is_time = abs(current_minutes - target_minutes) <= 120

        print(f"[SIM] 알림 시간 체크: 설정={notification_time}, 현재={current_time.strftime('%H:%M')}, 결과={is_time}")
        return is_time

    except Exception as e:
        print(f"[SIM] 알림 시간 확인 오류: {str(e)}")
        return False

def run_scheduler_simulation():
    """전체 스케줄러 시뮬레이션 실행"""
    print("=== 텔레그램 스케줄러 시뮬레이션 시작 ===")

    # 모의 데이터 생성
    now = datetime.now()

    mock_posts = [
        MockPost(1, "A 브랜드 캠페인", "2025-09-24"),      # 내일 마감
        MockPost(2, "B 제품 리뷰", "2025-09-25 15:30"),   # 모레 15:30 마감
        MockPost(3, "C 회사 협찬", "2025-09-22"),         # 어제 마감 (지난 것)
        MockPost(4, "D 이벤트", "2025-09-30"),           # 일주일 후 마감
        MockPost(5, "E 프로모션", "2025-09-23"),         # 오늘 마감
    ]

    mock_campaigns = [
        MockCampaign(1, 1, "캠페인 A"),
        MockCampaign(2, 1, "캠페인 B"),
        MockCampaign(3, 1, "캠페인 C"),
        MockCampaign(4, 2, "캠페인 D"),  # 다른 사용자 캠페인
        MockCampaign(5, 1, "캠페인 E"),
    ]

    mock_users = [
        MockUser(1, "김관리자", "admin@brandflow.com"),
        MockUser(2, "박직원", "staff@brandflow.com"),
    ]

    mock_telegram_settings = [
        MockTelegramSetting(1, "123456789", 3, "09:00"),
        MockTelegramSetting(2, "987654321", 1, "14:00"),
    ]

    print(f"시뮬레이션 데이터:")
    print(f"- Posts: {len(mock_posts)}개")
    print(f"- Campaigns: {len(mock_campaigns)}개")
    print(f"- Users: {len(mock_users)}개")
    print(f"- Telegram Settings: {len(mock_telegram_settings)}개")
    print()

    # 각 사용자별로 알림 확인 시뮬레이션
    for telegram_setting in mock_telegram_settings:
        user = next(u for u in mock_users if u.id == telegram_setting.user_id)

        print(f"=== 사용자 {user.name} (ID: {user.id}) 알림 확인 ===")

        # 알림 시간 확인
        if not simulate_is_notification_time(telegram_setting.notification_time):
            print(f"[SIM] 알림 시간이 아님 - 스킵")
            continue

        # 마감일 임박 posts 조회
        upcoming_posts = simulate_get_user_posts_with_upcoming_deadlines(
            user.id,
            telegram_setting.days_before_due,
            mock_posts,
            mock_campaigns
        )

        # 알림 전송 시뮬레이션
        for post, campaign, days_left in upcoming_posts:
            print(f"[SIM] 텔레그램 알림 전송:")
            print(f"      - 사용자: {user.name}")
            print(f"      - 채팅 ID: {telegram_setting.telegram_chat_id}")
            print(f"      - 캠페인: {post.title}")
            print(f"      - 마감일: {post.due_date}")
            print(f"      - 남은 시간: {days_left:.1f}일")
            print(f"      - 메시지: '{user.name}님, {post.title} 캠페인이 {abs(days_left):.1f}일 {'후' if days_left > 0 else '전'} 마감입니다!'")

        print()

    print("=== 시뮬레이션 완료 ===")

if __name__ == "__main__":
    try:
        run_scheduler_simulation()
        print("시뮬레이션 성공적으로 완료!")

    except Exception as e:
        print(f"시뮬레이션 중 오류: {e}")
        import traceback
        traceback.print_exc()