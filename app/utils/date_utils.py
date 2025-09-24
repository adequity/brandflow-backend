"""
날짜 처리 유틸리티 함수들
"""

from datetime import datetime, time
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def parse_due_datetime(
    due_date_str: str,
    default_time: str = "18:00",
    user_timezone: Optional[str] = None
) -> Optional[datetime]:
    """
    due_date 문자열을 정확한 datetime으로 변환

    Args:
        due_date_str: "2025-09-25" 또는 "2025-09-25 15:30" 형식
        default_time: 시간이 없을 때 사용할 기본 시간 (HH:MM)
        user_timezone: 사용자 시간대 (향후 확장용)

    Returns:
        datetime 객체 또는 None (파싱 실패시)

    Examples:
        >>> parse_due_datetime("2025-09-25")
        datetime(2025, 9, 25, 18, 0)  # 기본 18:00

        >>> parse_due_datetime("2025-09-25 15:30")
        datetime(2025, 9, 25, 15, 30)  # 지정된 시간
    """

    if not due_date_str or not due_date_str.strip():
        return None

    due_date_str = due_date_str.strip()

    try:
        # 케이스 1: "2025-09-25" (날짜만) → 기본 시간 추가
        if len(due_date_str) == 10 and due_date_str.count('-') == 2:
            logger.debug(f"[DATE_UTILS] 날짜만 파싱: {due_date_str} + {default_time}")
            return datetime.strptime(f"{due_date_str} {default_time}", "%Y-%m-%d %H:%M")

        # 케이스 2: "2025-09-25 15:30" (날짜+시간)
        elif len(due_date_str) == 16 and due_date_str.count('-') == 2 and due_date_str.count(':') == 1:
            logger.debug(f"[DATE_UTILS] 날짜+시간 파싱: {due_date_str}")
            return datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")

        # 케이스 3: "2025-09-25 15:30:00" (날짜+시간+초)
        elif len(due_date_str) == 19 and due_date_str.count('-') == 2 and due_date_str.count(':') == 2:
            logger.debug(f"[DATE_UTILS] 날짜+시간+초 파싱: {due_date_str}")
            return datetime.strptime(due_date_str, "%Y-%m-%d %H:%M:%S")

        # 케이스 4: ISO 형식 (T 포함)
        elif 'T' in due_date_str:
            logger.debug(f"[DATE_UTILS] ISO 형식 파싱: {due_date_str}")
            # "2025-09-25T15:30:00" 또는 "2025-09-25T15:30:00Z" 등
            clean_str = due_date_str.replace('Z', '').split('.')[0]  # 밀리초/타임존 제거
            if len(clean_str) == 19:  # YYYY-MM-DDTHH:MM:SS
                return datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
            elif len(clean_str) == 16:  # YYYY-MM-DDTHH:MM
                return datetime.strptime(clean_str, "%Y-%m-%dT%H:%M")

        else:
            logger.warning(f"[DATE_UTILS] 알 수 없는 날짜 형식: {due_date_str}")
            return None

    except ValueError as e:
        logger.error(f"[DATE_UTILS] 날짜 파싱 오류: {due_date_str} - {str(e)}")
        return None


def get_default_due_time_for_user(user_id: int) -> str:
    """
    사용자별 기본 마감시간 반환

    Args:
        user_id: 사용자 ID

    Returns:
        기본 마감시간 문자열 (HH:MM)
    """
    # 향후 사용자별 설정으로 확장 가능
    # 현재는 전역 기본값 사용
    return "18:00"


def format_due_datetime_for_display(dt: datetime) -> str:
    """
    datetime을 사용자 친화적 형식으로 포맷팅

    Args:
        dt: datetime 객체

    Returns:
        "2025-09-25 18:00" 형식 문자열
    """
    if not dt:
        return ""

    return dt.strftime("%Y-%m-%d %H:%M")


def calculate_time_until_due(due_datetime: datetime, current_time: Optional[datetime] = None) -> dict:
    """
    마감일까지 남은 시간 계산

    Args:
        due_datetime: 마감 일시
        current_time: 현재 시간 (None이면 현재 시간 사용)

    Returns:
        {
            'total_hours': float,  # 총 시간
            'total_days': float,   # 총 일수
            'is_overdue': bool,    # 마감 지남 여부
            'display_text': str    # 사용자 표시용 텍스트
        }
    """
    if not due_datetime:
        return {
            'total_hours': 0,
            'total_days': 0,
            'is_overdue': False,
            'display_text': '마감일 미설정'
        }

    if current_time is None:
        current_time = datetime.now()

    time_diff = due_datetime - current_time
    total_seconds = time_diff.total_seconds()
    total_hours = total_seconds / 3600
    total_days = total_hours / 24
    is_overdue = total_seconds < 0

    # 표시용 텍스트 생성
    if is_overdue:
        abs_hours = abs(total_hours)
        if abs_hours < 1:
            display_text = f"{int(abs(total_seconds / 60))}분 지남"
        elif abs_hours < 24:
            display_text = f"{abs_hours:.1f}시간 지남"
        else:
            display_text = f"{abs(total_days):.1f}일 지남"
    else:
        if total_hours < 1:
            display_text = f"{int(total_seconds / 60)}분 남음"
        elif total_hours < 24:
            display_text = f"{total_hours:.1f}시간 남음"
        else:
            display_text = f"{total_days:.1f}일 남음"

    return {
        'total_hours': total_hours,
        'total_days': total_days,
        'is_overdue': is_overdue,
        'display_text': display_text
    }


# 텔레그램 알림용 특화 함수
def should_send_telegram_notification(
    due_datetime: datetime,
    days_before_setting: int,
    current_time: Optional[datetime] = None,
    grace_period_hours: float = 12.0
) -> tuple[bool, float]:
    """
    텔레그램 알림을 보내야 하는지 판단

    Args:
        due_datetime: 마감 일시
        days_before_setting: 사용자 설정 (며칠 전 알림)
        current_time: 현재 시간
        grace_period_hours: 마감 후 알림 유예시간 (시간)

    Returns:
        (should_send: bool, days_left: float)
    """
    if not due_datetime:
        return False, 0.0

    time_info = calculate_time_until_due(due_datetime, current_time)
    days_left = time_info['total_days']

    # 알림 조건:
    # 1. 마감 전: days_before_setting 일 이내
    # 2. 마감 후: grace_period_hours 시간 이내
    grace_period_days = grace_period_hours / 24

    should_send = (-grace_period_days <= days_left <= days_before_setting)

    logger.debug(f"[DATE_UTILS] 알림 판단: days_left={days_left:.2f}, "
                f"setting={days_before_setting}, grace={grace_period_days:.2f}, "
                f"should_send={should_send}")

    return should_send, days_left