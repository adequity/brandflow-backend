from sqlalchemy.orm import Session
from app.models.system_setting import SystemSetting, SettingCategory, SettingType, AccessLevel
import logging

logger = logging.getLogger(__name__)


def init_system_settings(db: Session):
    """시스템 설정 초기 데이터 생성"""

    # 기본 시스템 설정들
    default_settings = [
        # 브랜딩 관련 설정
        {
            "setting_key": "branding.company_name",
            "display_name": "회사명",
            "description": "시스템에 표시될 회사명",
            "current_value": "BrandFlow",
            "default_value": "BrandFlow",
            "setting_type": SettingType.STRING,
            "category": SettingCategory.BRANDING,
            "access_level": AccessLevel.ADMIN,
            "is_system_default": True
        },
        {
            "setting_key": "branding.logo_url",
            "display_name": "로고 URL",
            "description": "시스템 로고 이미지 URL",
            "current_value": "",
            "default_value": "",
            "setting_type": SettingType.STRING,
            "category": SettingCategory.BRANDING,
            "access_level": AccessLevel.ADMIN,
            "is_system_default": True
        },
        {
            "setting_key": "branding.primary_color",
            "display_name": "기본 테마 색상",
            "description": "시스템 기본 색상 (#hex)",
            "current_value": "#3B82F6",
            "default_value": "#3B82F6",
            "setting_type": SettingType.STRING,
            "category": SettingCategory.BRANDING,
            "access_level": AccessLevel.ADMIN,
            "is_system_default": True
        },

        # 작업 유형 관련 설정
        {
            "setting_key": "worktype.auto_assignment",
            "display_name": "작업 자동 배정",
            "description": "신규 캠페인 생성 시 작업 자동 배정 여부",
            "current_value": "true",
            "default_value": "true",
            "setting_type": SettingType.BOOLEAN,
            "category": SettingCategory.WORKTYPE,
            "access_level": AccessLevel.ADMIN,
            "is_system_default": True
        },
        {
            "setting_key": "worktype.default_deadline_days",
            "display_name": "기본 마감일 (일)",
            "description": "신규 작업의 기본 마감일 (일 단위)",
            "current_value": "7",
            "default_value": "7",
            "setting_type": SettingType.NUMBER,
            "category": SettingCategory.WORKTYPE,
            "access_level": AccessLevel.ADMIN,
            "is_system_default": True
        },

        # 인센티브 관련 설정
        {
            "setting_key": "incentive.calculation_method",
            "display_name": "인센티브 계산 방식",
            "description": "인센티브 계산 방식 (percentage/fixed)",
            "current_value": "percentage",
            "default_value": "percentage",
            "setting_type": SettingType.STRING,
            "category": SettingCategory.INCENTIVE,
            "access_level": AccessLevel.SUPER_ADMIN,
            "is_system_default": True
        },
        {
            "setting_key": "incentive.default_rate",
            "display_name": "기본 인센티브율 (%)",
            "description": "기본 인센티브율 (백분율)",
            "current_value": "5.0",
            "default_value": "5.0",
            "setting_type": SettingType.NUMBER,
            "category": SettingCategory.INCENTIVE,
            "access_level": AccessLevel.SUPER_ADMIN,
            "is_system_default": True
        },

        # 영업 관련 설정
        {
            "setting_key": "sales.target_monthly",
            "display_name": "월간 매출 목표",
            "description": "월간 매출 목표 금액",
            "current_value": "10000000",
            "default_value": "10000000",
            "setting_type": SettingType.NUMBER,
            "category": SettingCategory.SALES,
            "access_level": AccessLevel.ADMIN,
            "is_system_default": True
        },
        {
            "setting_key": "sales.commission_rate",
            "display_name": "영업 수수료율 (%)",
            "description": "영업 수수료율 (백분율)",
            "current_value": "3.0",
            "default_value": "3.0",
            "setting_type": SettingType.NUMBER,
            "category": SettingCategory.SALES,
            "access_level": AccessLevel.ADMIN,
            "is_system_default": True
        },

        # 문서 관련 설정
        {
            "setting_key": "document.auto_backup",
            "display_name": "문서 자동 백업",
            "description": "문서 자동 백업 활성화 여부",
            "current_value": "true",
            "default_value": "true",
            "setting_type": SettingType.BOOLEAN,
            "category": SettingCategory.DOCUMENT,
            "access_level": AccessLevel.ADMIN,
            "is_system_default": True
        },
        {
            "setting_key": "document.retention_days",
            "display_name": "문서 보존 기간 (일)",
            "description": "삭제된 문서 보존 기간",
            "current_value": "30",
            "default_value": "30",
            "setting_type": SettingType.NUMBER,
            "category": SettingCategory.DOCUMENT,
            "access_level": AccessLevel.ADMIN,
            "is_system_default": True
        },

        # 일반 설정
        {
            "setting_key": "general.timezone",
            "display_name": "시간대",
            "description": "시스템 기본 시간대",
            "current_value": "Asia/Seoul",
            "default_value": "Asia/Seoul",
            "setting_type": SettingType.STRING,
            "category": SettingCategory.GENERAL,
            "access_level": AccessLevel.ADMIN,
            "is_system_default": True
        },
        {
            "setting_key": "general.language",
            "display_name": "기본 언어",
            "description": "시스템 기본 언어",
            "current_value": "ko",
            "default_value": "ko",
            "setting_type": SettingType.STRING,
            "category": SettingCategory.GENERAL,
            "access_level": AccessLevel.USER,
            "is_system_default": True
        },
        {
            "setting_key": "general.page_size",
            "display_name": "페이지당 항목 수",
            "description": "목록 페이지의 기본 항목 수",
            "current_value": "20",
            "default_value": "20",
            "setting_type": SettingType.NUMBER,
            "category": SettingCategory.GENERAL,
            "access_level": AccessLevel.USER,
            "is_system_default": True
        },

        # 데이터베이스 관련 설정 (슈퍼 어드민 전용)
        {
            "setting_key": "database.backup_interval_hours",
            "display_name": "백업 주기 (시간)",
            "description": "자동 백업 주기 (시간 단위)",
            "current_value": "24",
            "default_value": "24",
            "setting_type": SettingType.NUMBER,
            "category": SettingCategory.DATABASE,
            "access_level": AccessLevel.SUPER_ADMIN,
            "is_system_default": True
        },
        {
            "setting_key": "database.cleanup_old_logs",
            "display_name": "로그 자동 정리",
            "description": "오래된 로그 자동 정리 활성화",
            "current_value": "true",
            "default_value": "true",
            "setting_type": SettingType.BOOLEAN,
            "category": SettingCategory.DATABASE,
            "access_level": AccessLevel.SUPER_ADMIN,
            "is_system_default": True
        }
    ]

    try:
        for setting_data in default_settings:
            # 기존 설정이 있는지 확인
            existing = db.query(SystemSetting).filter(
                SystemSetting.setting_key == setting_data["setting_key"]
            ).first()

            if not existing:
                setting = SystemSetting(**setting_data)
                db.add(setting)
                logger.info(f"시스템 설정 생성: {setting_data['setting_key']}")

        db.commit()
        logger.info("시스템 설정 초기화 완료")

    except Exception as e:
        logger.error(f"시스템 설정 초기화 실패: {str(e)}")
        db.rollback()
        raise