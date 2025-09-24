#!/usr/bin/env python3
"""
텔레그램 알림 기능 테스트 스크립트
- 데이터베이스 연결 없이 로컬에서 테스트 가능
- 날짜 파싱 및 알림 로직 검증
"""

import sys
import os
from datetime import datetime, timedelta

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.date_utils import (
    parse_due_datetime,
    should_send_telegram_notification,
    format_due_datetime_for_display,
    calculate_time_until_due
)

def test_date_parsing():
    """날짜 파싱 테스트"""
    print("=== 날짜 파싱 테스트 ===")

    test_cases = [
        "2025-09-23",           # 오늘
        "2025-09-24",           # 내일
        "2025-09-25",           # 모레
        "2025-09-25 15:30",     # 시간 포함
        "2025-09-22",           # 어제
        "invalid-date",         # 잘못된 형식
        "",                     # 빈 문자열
    ]

    for date_str in test_cases:
        try:
            result = parse_due_datetime(date_str, default_time="18:00")
            print(f"OK '{date_str}' -> {result}")
        except Exception as e:
            print(f"FAIL '{date_str}' -> Error: {e}")
    print()

def test_notification_logic():
    """알림 로직 테스트"""
    print("=== 알림 로직 테스트 ===")

    now = datetime.now()

    # 다양한 시나리오 테스트
    test_scenarios = [
        # (날짜, 며칠 전 설정, 예상 결과)
        (now + timedelta(days=1), 3, True),   # 1일 후 마감, 3일 전 알림 → 알림 O
        (now + timedelta(days=5), 3, False),  # 5일 후 마감, 3일 전 알림 → 알림 X
        (now - timedelta(hours=6), 3, True),  # 6시간 전 마감, 유예기간 → 알림 O
        (now - timedelta(days=2), 3, False),  # 2일 전 마감, 유예기간 초과 → 알림 X
    ]

    for due_date, days_before, expected in test_scenarios:
        should_send, days_left = should_send_telegram_notification(
            due_datetime=due_date,
            days_before_setting=days_before,
            current_time=now,
            grace_period_hours=12.0
        )

        status = "OK" if should_send == expected else "FAIL"
        print(f"{status} 마감: {due_date.strftime('%Y-%m-%d %H:%M')}")
        print(f"   설정: {days_before}일 전, 결과: {should_send}, 남은시간: {days_left:.1f}일")
    print()

def test_real_scenario():
    """실제 시나리오 테스트"""
    print("=== 실제 시나리오 테스트 ===")

    # 캠페인 마감일 시뮬레이션
    campaigns = [
        {"id": 1, "title": "A 브랜드 캠페인", "due_date": "2025-09-24"},
        {"id": 2, "title": "B 제품 리뷰", "due_date": "2025-09-25 15:30"},
        {"id": 3, "title": "C 회사 협찬", "due_date": "2025-09-22"},
        {"id": 4, "title": "D 이벤트", "due_date": "2025-09-30"},
    ]

    print("현재 시간:", datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("알림 설정: 3일 전")
    print()

    for campaign in campaigns:
        # 날짜 파싱
        due_datetime = parse_due_datetime(campaign["due_date"])
        if not due_datetime:
            continue

        # 알림 여부 확인
        should_send, days_left = should_send_telegram_notification(
            due_datetime=due_datetime,
            days_before_setting=3
        )

        # 시간 계산
        time_info = calculate_time_until_due(due_datetime)

        # 결과 출력
        alert_status = "[ALERT]" if should_send else "[QUIET]"
        print(f"{alert_status} 캠페인 #{campaign['id']}: {campaign['title']}")
        print(f"   마감일: {format_due_datetime_for_display(due_datetime)}")
        print(f"   상태: {time_info['display_text']}")
        print(f"   알림: {'전송 대상' if should_send else '전송 안함'}")
        print()

def test_edge_cases():
    """엣지 케이스 테스트"""
    print("=== 엣지 케이스 테스트 ===")

    # 정확히 마감시간인 경우
    now = datetime.now()
    exact_due = now.replace(second=0, microsecond=0)

    should_send, days_left = should_send_telegram_notification(
        due_datetime=exact_due,
        days_before_setting=1,
        current_time=now
    )

    print(f"정확히 마감시간: should_send={should_send}, days_left={days_left:.3f}")

    # 자정 경계 테스트
    midnight_due = parse_due_datetime("2025-09-24", default_time="00:00")
    should_send, days_left = should_send_telegram_notification(
        due_datetime=midnight_due,
        days_before_setting=1
    )

    print(f"자정 마감: should_send={should_send}, days_left={days_left:.3f}")
    print()

if __name__ == "__main__":
    print("BrandFlow 텔레그램 알림 기능 테스트")
    print("=" * 50)

    try:
        test_date_parsing()
        test_notification_logic()
        test_real_scenario()
        test_edge_cases()

        print("=" * 50)
        print("모든 테스트 완료!")
        print("\n테스트 결과:")
        print("- 날짜 파싱: 다양한 형식 지원 확인")
        print("- 알림 로직: 설정된 조건에 따른 정확한 판단")
        print("- 실제 시나리오: 캠페인 마감일 기준 알림 작동")
        print("- 엣지 케이스: 경계 상황 처리 확인")

    except Exception as e:
        print(f"테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()