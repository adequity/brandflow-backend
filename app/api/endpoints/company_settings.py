from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.company_settings import CompanySettings, CompanyInfo
from app.models.system_setting import SettingCategory
from app.services.company_settings import (
    get_user_company,
    can_user_edit_company_settings
)

router = APIRouter()


@router.get("/")
async def get_company_settings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """현재 사용자 회사의 설정 목록 조회"""

    user_company = get_user_company(user)

    if user_company is None:
        raise HTTPException(status_code=400, detail="사용자에게 회사 정보가 없습니다")

    # 회사별 설정 조회
    settings = db.query(CompanySettings).filter(
        CompanySettings.company == user_company
    ).all()

    # 딕셔너리로 변환
    settings_dict = {}
    for setting in settings:
        settings_dict[setting.setting_key] = setting.setting_value

    return {
        "success": True,
        "company": user_company,
        "settings": settings_dict
    }


@router.post("/bulk-update")
async def bulk_update_company_settings(
    settings: Dict[str, str] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """현재 사용자 회사의 설정 일괄 업데이트"""

    user_company = get_user_company(user)

    if user_company is None:
        raise HTTPException(status_code=400, detail="사용자에게 회사 정보가 없습니다")

    if not can_user_edit_company_settings(user, user_company):
        raise HTTPException(status_code=403, detail="회사 설정을 수정할 권한이 없습니다")

    updated_settings = []
    errors = []

    for setting_key, new_value in settings.items():
        try:
            # 기존 설정 확인
            existing_setting = db.query(CompanySettings).filter(
                CompanySettings.company == user_company,
                CompanySettings.setting_key == setting_key
            ).first()

            if existing_setting:
                # 기존 설정 업데이트
                existing_setting.setting_value = new_value
                existing_setting.modified_by = user.id
                existing_setting.updated_at = datetime.utcnow()
            else:
                # 새 설정 생성
                new_setting = CompanySettings(
                    company=user_company,
                    setting_key=setting_key,
                    setting_value=new_value,
                    modified_by=user.id
                )
                db.add(new_setting)

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


@router.get("/info")
async def get_company_info(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """현재 사용자 회사의 정보를 DocumentTemplateBuilder 형태로 반환"""

    user_company = get_user_company(user)

    if user_company is None:
        raise HTTPException(status_code=400, detail="사용자에게 회사 정보가 없습니다")

    # 회사별 설정 조회
    settings = db.query(CompanySettings).filter(
        CompanySettings.company == user_company
    ).all()

    # CompanyInfo 헬퍼 클래스 사용
    settings_dict = {}
    for setting in settings:
        settings_dict[setting.setting_key] = setting.setting_value

    company_info = CompanyInfo(user_company, settings_dict)

    return {
        "success": True,
        "company": user_company,
        "info": company_info.to_dict()
    }


@router.get("/{setting_key}")
async def get_company_setting(
    setting_key: str = Path(..., description="설정 키"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """특정 회사 설정 조회"""

    user_company = get_user_company(user)

    if user_company is None:
        raise HTTPException(status_code=400, detail="사용자에게 회사 정보가 없습니다")

    setting = db.query(CompanySettings).filter(
        CompanySettings.company == user_company,
        CompanySettings.setting_key == setting_key
    ).first()

    if not setting:
        return {
            "success": True,
            "setting_key": setting_key,
            "setting_value": None
        }

    return {
        "success": True,
        "setting_key": setting.setting_key,
        "setting_value": setting.setting_value
    }


@router.put("/{setting_key}")
async def update_company_setting(
    setting_key: str = Path(..., description="설정 키"),
    setting_value: str = Body(..., description="설정 값"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """특정 회사 설정 업데이트"""

    user_company = get_user_company(user)

    if user_company is None:
        raise HTTPException(status_code=400, detail="사용자에게 회사 정보가 없습니다")

    if not can_user_edit_company_settings(user, user_company):
        raise HTTPException(status_code=403, detail="회사 설정을 수정할 권한이 없습니다")

    # 기존 설정 확인
    setting = db.query(CompanySettings).filter(
        CompanySettings.company == user_company,
        CompanySettings.setting_key == setting_key
    ).first()

    if setting:
        # 기존 설정 업데이트
        setting.setting_value = setting_value
        setting.modified_by = user.id
        setting.updated_at = datetime.utcnow()
    else:
        # 새 설정 생성
        setting = CompanySettings(
            company=user_company,
            setting_key=setting_key,
            setting_value=setting_value,
            modified_by=user.id
        )
        db.add(setting)

    db.commit()
    db.refresh(setting)

    return {
        "success": True,
        "setting_key": setting.setting_key,
        "setting_value": setting.setting_value
    }


@router.delete("/{setting_key}")
async def delete_company_setting(
    setting_key: str = Path(..., description="설정 키"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """특정 회사 설정 삭제"""

    user_company = get_user_company(user)

    if user_company is None:
        raise HTTPException(status_code=400, detail="사용자에게 회사 정보가 없습니다")

    if not can_user_edit_company_settings(user, user_company):
        raise HTTPException(status_code=403, detail="회사 설정을 수정할 권한이 없습니다")

    setting = db.query(CompanySettings).filter(
        CompanySettings.company == user_company,
        CompanySettings.setting_key == setting_key
    ).first()

    if not setting:
        raise HTTPException(status_code=404, detail="설정을 찾을 수 없습니다")

    db.delete(setting)
    db.commit()

    return {
        "success": True,
        "message": f"설정 '{setting_key}'가 삭제되었습니다"
    }