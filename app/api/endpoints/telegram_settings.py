from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from typing import List, Optional
from datetime import datetime, date, timedelta

from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.user_telegram_setting import UserTelegramSetting, TelegramNotificationLog
from app.schemas.telegram_setting import (
    TelegramSettingCreate,
    TelegramSettingUpdate,
    TelegramSettingResponse,
    TelegramTestRequest,
    TelegramNotificationLogResponse,
    TelegramStatsResponse
)
from app.services.telegram_service import telegram_service, validate_telegram_chat_id

router = APIRouter()


@router.get("/my-setting", response_model=Optional[TelegramSettingResponse])
async def get_my_telegram_setting(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """현재 사용자의 텔레그램 설정 조회"""

    setting = db.query(UserTelegramSetting).filter(
        UserTelegramSetting.user_id == user.id
    ).first()

    return setting


@router.post("/my-setting", response_model=TelegramSettingResponse)
async def create_or_update_my_telegram_setting(
    setting_data: TelegramSettingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """현재 사용자의 텔레그램 설정 생성 또는 업데이트"""

    # 텔레그램 채팅 ID 유효성 검증
    is_valid = await validate_telegram_chat_id(setting_data.telegram_chat_id)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="유효하지 않은 텔레그램 채팅 ID입니다. 봇과 대화를 시작한 후 채팅 ID를 확인해 주세요."
        )

    # 기존 설정 확인
    existing_setting = db.query(UserTelegramSetting).filter(
        UserTelegramSetting.user_id == user.id
    ).first()

    if existing_setting:
        # 업데이트
        for field, value in setting_data.dict().items():
            setattr(existing_setting, field, value)

        existing_setting.updated_at = datetime.utcnow()
        setting = existing_setting
    else:
        # 새로 생성
        setting = UserTelegramSetting(
            user_id=user.id,
            **setting_data.dict()
        )
        db.add(setting)

    db.commit()
    db.refresh(setting)

    return setting


@router.put("/my-setting", response_model=TelegramSettingResponse)
async def update_my_telegram_setting(
    setting_data: TelegramSettingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """현재 사용자의 텔레그램 설정 업데이트"""

    setting = db.query(UserTelegramSetting).filter(
        UserTelegramSetting.user_id == user.id
    ).first()

    if not setting:
        raise HTTPException(status_code=404, detail="텔레그램 설정을 찾을 수 없습니다")

    # 채팅 ID가 변경되는 경우 유효성 검증
    if setting_data.telegram_chat_id and setting_data.telegram_chat_id != setting.telegram_chat_id:
        is_valid = await validate_telegram_chat_id(setting_data.telegram_chat_id)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail="유효하지 않은 텔레그램 채팅 ID입니다."
            )

    # 업데이트
    update_data = setting_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(setting, field, value)

    setting.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(setting)

    return setting


@router.delete("/my-setting")
async def delete_my_telegram_setting(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """현재 사용자의 텔레그램 설정 삭제"""

    setting = db.query(UserTelegramSetting).filter(
        UserTelegramSetting.user_id == user.id
    ).first()

    if not setting:
        raise HTTPException(status_code=404, detail="텔레그램 설정을 찾을 수 없습니다")

    db.delete(setting)
    db.commit()

    return {"message": "텔레그램 설정이 삭제되었습니다"}


@router.post("/test")
async def send_test_telegram_message(
    test_data: TelegramTestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """텔레그램 테스트 메시지 전송"""

    setting = db.query(UserTelegramSetting).filter(
        UserTelegramSetting.user_id == user.id
    ).first()

    if not setting:
        raise HTTPException(
            status_code=404,
            detail="텔레그램 설정을 먼저 등록해 주세요"
        )

    if not setting.is_enabled:
        raise HTTPException(
            status_code=400,
            detail="텔레그램 알림이 비활성화되어 있습니다"
        )

    # 테스트 메시지 전송
    if test_data.message == "테스트 메시지입니다.":
        # 기본 테스트 메시지
        result = await telegram_service.send_test_message(
            setting.telegram_chat_id,
            user.name
        )
    else:
        # 사용자 지정 메시지
        result = await telegram_service.send_message(
            setting.telegram_chat_id,
            test_data.message
        )

    if result.get("success"):
        # 성공 로그 저장
        log = TelegramNotificationLog(
            user_id=user.id,
            post_id=0,  # 테스트 메시지는 post_id가 없음
            campaign_id=0,  # 테스트 메시지는 campaign_id가 없음
            notification_type="test_message",
            message_content=test_data.message,
            telegram_chat_id=setting.telegram_chat_id,
            is_sent=True,
            sent_at=datetime.utcnow(),
            telegram_message_id=str(result.get("message_id", ""))
        )
        db.add(log)
        db.commit()

        return {
            "success": True,
            "message": "테스트 메시지가 성공적으로 전송되었습니다!",
            "telegram_message_id": result.get("message_id")
        }
    else:
        # 실패 로그 저장
        log = TelegramNotificationLog(
            user_id=user.id,
            post_id=0,
            campaign_id=0,
            notification_type="test_message",
            message_content=test_data.message,
            telegram_chat_id=setting.telegram_chat_id,
            is_sent=False,
            error_message=result.get("error", "알 수 없는 오류")
        )
        db.add(log)
        db.commit()

        raise HTTPException(
            status_code=400,
            detail=f"메시지 전송 실패: {result.get('error', '알 수 없는 오류')}"
        )


@router.get("/logs", response_model=List[TelegramNotificationLogResponse])
async def get_my_telegram_logs(
    limit: int = Query(20, ge=1, le=100, description="조회할 로그 수"),
    offset: int = Query(0, ge=0, description="조회 시작 위치"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """현재 사용자의 텔레그램 알림 로그 조회"""

    logs = db.query(TelegramNotificationLog).filter(
        TelegramNotificationLog.user_id == user.id
    ).order_by(desc(TelegramNotificationLog.created_at)).offset(offset).limit(limit).all()

    return logs


@router.get("/stats", response_model=TelegramStatsResponse)
async def get_telegram_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """텔레그램 알림 통계 (관리자용)"""

    if user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")

    today = date.today()

    # 전체 텔레그램 설정 사용자 수
    total_users = db.query(UserTelegramSetting).count()

    # 활성화된 알림 수
    active_notifications = db.query(UserTelegramSetting).filter(
        UserTelegramSetting.is_enabled == True
    ).count()

    # 오늘 발송된 알림 수
    notifications_sent_today = db.query(TelegramNotificationLog).filter(
        and_(
            func.date(TelegramNotificationLog.created_at) == today,
            TelegramNotificationLog.is_sent == True
        )
    ).count()

    # 오늘 실패한 알림 수
    notifications_failed_today = db.query(TelegramNotificationLog).filter(
        and_(
            func.date(TelegramNotificationLog.created_at) == today,
            TelegramNotificationLog.is_sent == False
        )
    ).count()

    # 향후 마감일 임박한 posts 수 (간단 계산)
    upcoming_deadlines = 0  # 추후 구현

    return TelegramStatsResponse(
        total_users_with_telegram=total_users,
        active_notifications=active_notifications,
        notifications_sent_today=notifications_sent_today,
        notifications_failed_today=notifications_failed_today,
        upcoming_deadlines=upcoming_deadlines
    )


@router.get("/admin/all-settings")
async def get_all_telegram_settings(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    is_enabled: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """모든 사용자의 텔레그램 설정 조회 (관리자용)"""

    if user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")

    query = db.query(UserTelegramSetting).join(User)

    if is_enabled is not None:
        query = query.filter(UserTelegramSetting.is_enabled == is_enabled)

    total = query.count()
    settings = query.offset((page - 1) * size).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "settings": settings
    }


@router.post("/test-deadline-notifications")
async def test_deadline_notifications(
    force_all: bool = Query(False, description="모든 알림 시간대에서 강제 실행"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """텔레그램 마감일 알림 테스트 (관리자용)"""

    if user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")

    from app.services.telegram_scheduler import telegram_scheduler

    try:
        # 원래 is_notification_time 함수 백업
        original_is_notification_time = telegram_scheduler.is_notification_time

        if force_all:
            # 강제 실행: 모든 시간대에서 알림 허용
            telegram_scheduler.is_notification_time = lambda time_str: True

        # 알림 체크 및 전송 실행
        await telegram_scheduler.check_and_send_notifications()

        # 원래 함수 복원
        if force_all:
            telegram_scheduler.is_notification_time = original_is_notification_time

        return {
            "success": True,
            "message": "텔레그램 마감일 알림 테스트가 완료되었습니다.",
            "force_all": force_all,
            "executed_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        # 오류 발생시 원래 함수 복원
        if force_all:
            telegram_scheduler.is_notification_time = original_is_notification_time

        raise HTTPException(
            status_code=500,
            detail=f"알림 테스트 실행 중 오류: {str(e)}"
        )