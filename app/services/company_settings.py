from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from app.models.system_setting import SystemSetting, SettingCategory
from app.models.company_settings import CompanySettings, CompanyInfo
from app.models.user import User, UserRole


def get_user_company(user: User) -> Optional[str]:
    """사용자의 회사 정보를 반환합니다.

    - SUPER_ADMIN: None (전역 설정 접근)
    - AGENCY_ADMIN: 본인 회사
    - STAFF: 본인 회사
    - CLIENT: 본인 회사
    """
    if user.role == UserRole.SUPER_ADMIN:
        return None  # 전역 설정에 접근
    return user.company


def get_company_settings(db: Session, company: str, setting_key: Optional[str] = None) -> List[CompanySettings]:
    """특정 회사의 설정들을 조회합니다."""
    query = db.query(CompanySettings).filter(CompanySettings.company == company)

    if setting_key:
        query = query.filter(CompanySettings.setting_key == setting_key)

    return query.all()


def get_company_setting_value(db: Session, company: str, setting_key: str) -> Optional[str]:
    """특정 회사의 특정 설정 값을 조회합니다."""
    company_setting = db.query(CompanySettings).filter(
        CompanySettings.company == company,
        CompanySettings.setting_key == setting_key
    ).first()

    if company_setting:
        return company_setting.setting_value

    return None


def set_company_setting(db: Session, company: str, setting_key: str, value: str, user: User) -> CompanySettings:
    """회사별 설정을 생성하거나 업데이트합니다."""
    # 기존 회사별 설정 확인
    existing = db.query(CompanySettings).filter(
        CompanySettings.company == company,
        CompanySettings.setting_key == setting_key
    ).first()

    if existing:
        # 업데이트
        existing.setting_value = value
        existing.modified_by = user.id
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # 새로운 회사별 설정 생성
        new_setting = CompanySettings(
            company=company,
            setting_key=setting_key,
            setting_value=value,
            modified_by=user.id
        )

        db.add(new_setting)
        db.commit()
        db.refresh(new_setting)
        return new_setting


def get_company_info_dict(db: Session, company: str) -> Dict[str, str]:
    """회사 정보를 딕셔너리 형태로 반환합니다. (DocumentTemplateBuilder용)"""
    company_settings = get_company_settings(db, company)

    # CompanyInfo 헬퍼 클래스 사용
    settings_dict = {}
    for setting in company_settings:
        settings_dict[setting.setting_key] = setting.setting_value

    company_info = CompanyInfo(company, settings_dict)
    return company_info.to_dict()


def can_user_edit_company_settings(user: User, target_company: str) -> bool:
    """사용자가 특정 회사의 설정을 편집할 수 있는지 확인합니다."""
    if user.role == UserRole.SUPER_ADMIN:
        return True  # 슈퍼 어드민은 모든 회사 설정 가능

    if user.role == UserRole.AGENCY_ADMIN:
        return user.company == target_company  # 본인 회사만 편집 가능

    return False  # STAFF, CLIENT는 편집 불가