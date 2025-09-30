from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, date

from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.system_setting import SystemSetting, SettingCategory, SettingType, AccessLevel
from app.schemas.system_setting import (
    SystemSettingCreate,
    SystemSettingUpdate,
    SystemSettingResponse,
    SystemSettingListResponse,
    SystemSettingBulkUpdate,
    SystemSettingStats
)

router = APIRouter()


def check_setting_access(user: User, setting: SystemSetting, operation: str = "read") -> bool:
    """설정 접근 권한 확인"""
    if user.role == UserRole.SUPER_ADMIN:
        return True

    if setting.access_level == AccessLevel.SUPER_ADMIN:
        return False

    if setting.access_level == AccessLevel.ADMIN and user.role == UserRole.AGENCY_ADMIN:
        return True

    if setting.access_level == AccessLevel.USER:
        return True

    return False


@router.get("/", response_model=SystemSettingListResponse)
async def get_system_settings(
    category: Optional[SettingCategory] = Query(None, description="카테고리별 필터"),
    access_level: Optional[AccessLevel] = Query(None, description="접근 레벨별 필터"),
    is_active: Optional[bool] = Query(None, description="활성 상태 필터"),
    search: Optional[str] = Query(None, description="설정명/키 검색"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(50, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """시스템 설정 목록 조회"""

    # 기본 쿼리
    query = db.query(SystemSetting)

    # 필터 적용
    if category:
        query = query.filter(SystemSetting.category == category)

    if access_level:
        query = query.filter(SystemSetting.access_level == access_level)

    if is_active is not None:
        query = query.filter(SystemSetting.is_active == is_active)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (SystemSetting.setting_key.ilike(search_filter)) |
            (SystemSetting.display_name.ilike(search_filter))
        )

    # 권한 필터링 (슈퍼 어드민이 아닌 경우)
    if user.role != UserRole.SUPER_ADMIN:
        if user.role in [UserRole.AGENCY_ADMIN]:
            # 어드민은 슈퍼 어드민 전용 설정 제외
            query = query.filter(SystemSetting.access_level != AccessLevel.SUPER_ADMIN)
        else:
            # 일반 사용자는 USER 레벨만 조회 가능
            query = query.filter(SystemSetting.access_level == AccessLevel.USER)

    # 총 개수 계산
    total = query.count()

    # 페이징 및 정렬
    settings = query.order_by(
        SystemSetting.category,
        SystemSetting.setting_key
    ).offset((page - 1) * size).limit(size).all()

    return SystemSettingListResponse(
        total=total,
        settings=settings
    )


@router.get("/stats", response_model=SystemSettingStats)
async def get_system_settings_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """시스템 설정 통계"""

    base_query = db.query(SystemSetting)

    # 권한 필터링
    if user.role != UserRole.SUPER_ADMIN:
        if user.role in [UserRole.AGENCY_ADMIN]:
            base_query = base_query.filter(SystemSetting.access_level != AccessLevel.SUPER_ADMIN)
        else:
            base_query = base_query.filter(SystemSetting.access_level == AccessLevel.USER)

    # 기본 통계
    total_settings = base_query.count()
    active_settings = base_query.filter(SystemSetting.is_active == True).count()

    # 카테고리별 통계
    category_stats = dict(
        base_query.with_entities(
            SystemSetting.category,
            func.count(SystemSetting.id)
        ).group_by(SystemSetting.category).all()
    )

    # 접근 레벨별 통계
    access_level_stats = dict(
        base_query.with_entities(
            SystemSetting.access_level,
            func.count(SystemSetting.id)
        ).group_by(SystemSetting.access_level).all()
    )

    # 타입별 통계
    type_stats = dict(
        base_query.with_entities(
            SystemSetting.setting_type,
            func.count(SystemSetting.id)
        ).group_by(SystemSetting.setting_type).all()
    )

    # 오늘 수정된 설정 수
    today = date.today()
    modified_today = base_query.filter(
        func.date(SystemSetting.updated_at) == today
    ).count()

    return SystemSettingStats(
        total_settings=total_settings,
        active_settings=active_settings,
        by_category={str(k): v for k, v in category_stats.items()},
        by_access_level={str(k): v for k, v in access_level_stats.items()},
        by_type={str(k): v for k, v in type_stats.items()},
        modified_today=modified_today
    )


@router.get("/{setting_key}", response_model=SystemSettingResponse)
async def get_system_setting(
    setting_key: str = Path(..., description="설정 키"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """특정 시스템 설정 조회"""

    setting = db.query(SystemSetting).filter(
        SystemSetting.setting_key == setting_key
    ).first()

    if not setting:
        raise HTTPException(status_code=404, detail="설정을 찾을 수 없습니다")

    if not check_setting_access(user, setting, "read"):
        raise HTTPException(status_code=403, detail="설정에 접근할 권한이 없습니다")

    return setting


@router.post("/", response_model=SystemSettingResponse)
async def create_system_setting(
    setting_data: SystemSettingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """새 시스템 설정 생성"""

    # 권한 확인 (어드민 이상만 생성 가능)
    if user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="설정 생성 권한이 없습니다")

    # 슈퍼 어드민 전용 설정은 슈퍼 어드민만 생성 가능
    if setting_data.access_level == AccessLevel.SUPER_ADMIN and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="슈퍼 어드민 전용 설정을 생성할 권한이 없습니다")

    # 중복 키 확인
    existing = db.query(SystemSetting).filter(
        SystemSetting.setting_key == setting_data.setting_key
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="이미 존재하는 설정 키입니다")

    # 설정 생성
    setting = SystemSetting(
        **setting_data.dict(),
        modified_by=user.id
    )

    db.add(setting)
    db.commit()
    db.refresh(setting)

    return setting


@router.put("/{setting_key}", response_model=SystemSettingResponse)
async def update_system_setting(
    setting_key: str = Path(..., description="설정 키"),
    setting_data: SystemSettingUpdate = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """시스템 설정 수정"""

    setting = db.query(SystemSetting).filter(
        SystemSetting.setting_key == setting_key
    ).first()

    if not setting:
        raise HTTPException(status_code=404, detail="설정을 찾을 수 없습니다")

    if not check_setting_access(user, setting, "write"):
        raise HTTPException(status_code=403, detail="설정을 수정할 권한이 없습니다")

    # 시스템 기본 설정의 특정 필드는 수정 제한
    if setting.is_system_default:
        restricted_fields = {'access_level', 'is_active'}
        update_fields = set(setting_data.dict(exclude_unset=True).keys())
        if restricted_fields.intersection(update_fields) and user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=403,
                detail="시스템 기본 설정의 접근 레벨이나 활성 상태는 슈퍼 어드민만 변경할 수 있습니다"
            )

    # 설정 업데이트
    update_data = setting_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(setting, field, value)

    setting.modified_by = user.id
    setting.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(setting)

    return setting


@router.post("/bulk-update")
async def bulk_update_settings(
    bulk_data: SystemSettingBulkUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """여러 설정 일괄 업데이트"""

    if user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="설정을 수정할 권한이 없습니다")

    updated_settings = []
    errors = []

    for setting_key, new_value in bulk_data.settings.items():
        try:
            setting = db.query(SystemSetting).filter(
                SystemSetting.setting_key == setting_key
            ).first()

            if not setting:
                errors.append(f"설정 '{setting_key}'를 찾을 수 없습니다")
                continue

            if not check_setting_access(user, setting, "write"):
                errors.append(f"설정 '{setting_key}'에 접근할 권한이 없습니다")
                continue

            # 값 유형 검증
            if setting.setting_type == SettingType.BOOLEAN:
                new_value = str(new_value).lower() in ('true', '1', 'yes', 'on')
            elif setting.setting_type == SettingType.NUMBER:
                try:
                    float(new_value) if '.' in str(new_value) else int(new_value)
                except (ValueError, TypeError):
                    errors.append(f"설정 '{setting_key}'의 값이 숫자 형식이 아닙니다")
                    continue
            elif setting.setting_type == SettingType.JSON:
                try:
                    import json
                    json.loads(str(new_value)) if isinstance(new_value, str) else new_value
                except json.JSONDecodeError:
                    errors.append(f"설정 '{setting_key}'의 값이 유효한 JSON 형식이 아닙니다")
                    continue

            setting.current_value = str(new_value)
            setting.modified_by = user.id
            setting.updated_at = datetime.utcnow()

            updated_settings.append(setting_key)

        except Exception as e:
            errors.append(f"설정 '{setting_key}' 업데이트 중 오류: {str(e)}")

    if updated_settings:
        db.commit()

    return {
        "success": True,
        "updated_settings": updated_settings,
        "errors": errors,
        "total_updated": len(updated_settings),
        "total_errors": len(errors)
    }


@router.delete("/{setting_key}")
async def delete_system_setting(
    setting_key: str = Path(..., description="설정 키"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """시스템 설정 삭제"""

    if user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="설정 삭제는 슈퍼 어드민만 가능합니다")

    setting = db.query(SystemSetting).filter(
        SystemSetting.setting_key == setting_key
    ).first()

    if not setting:
        raise HTTPException(status_code=404, detail="설정을 찾을 수 없습니다")

    if setting.is_system_default:
        raise HTTPException(status_code=400, detail="시스템 기본 설정은 삭제할 수 없습니다")

    db.delete(setting)
    db.commit()

    return {"message": f"설정 '{setting_key}'가 삭제되었습니다"}


@router.post("/reset/{setting_key}")
async def reset_setting_to_default(
    setting_key: str = Path(..., description="설정 키"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """설정을 기본값으로 초기화"""

    setting = db.query(SystemSetting).filter(
        SystemSetting.setting_key == setting_key
    ).first()

    if not setting:
        raise HTTPException(status_code=404, detail="설정을 찾을 수 없습니다")

    if not check_setting_access(user, setting, "write"):
        raise HTTPException(status_code=403, detail="설정을 수정할 권한이 없습니다")

    setting.current_value = setting.default_value
    setting.modified_by = user.id
    setting.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(setting)

    return setting