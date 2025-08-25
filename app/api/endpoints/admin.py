"""
관리자 전용 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_db
from app.db.cleanup_data import cleanup_dummy_data, reset_database_to_production
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole

router = APIRouter()


@router.post("/cleanup-dummy-data")
async def cleanup_dummy_data_endpoint(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """더미 데이터 정리 (슈퍼 어드민 전용)"""
    
    # 슈퍼 어드민 권한 확인
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="슈퍼 어드민만 더미 데이터를 정리할 수 있습니다."
        )
    
    try:
        await cleanup_dummy_data(db)
        return {
            "message": "더미 데이터가 성공적으로 정리되었습니다.",
            "details": "슈퍼 어드민 계정만 남겨두고 모든 테스트 데이터가 삭제되었습니다."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"더미 데이터 정리 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/reset-to-production")
async def reset_to_production_endpoint(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """프로덕션 환경으로 데이터베이스 초기화 (슈퍼 어드민 전용)"""
    
    # 슈퍼 어드민 권한 확인
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="슈퍼 어드민만 프로덕션 초기화를 실행할 수 있습니다."
        )
    
    try:
        await reset_database_to_production(db)
        return {
            "message": "데이터베이스가 프로덕션 환경으로 성공적으로 초기화되었습니다.",
            "details": "슈퍼 어드민 계정만 존재하며, 모든 더미 데이터는 제거되었습니다."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"프로덕션 초기화 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/system-status")
async def get_system_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """시스템 상태 조회 (슈퍼 어드민 전용)"""
    
    # 슈퍼 어드민 권한 확인
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="슈퍼 어드민만 시스템 상태를 조회할 수 있습니다."
        )
    
    try:
        from sqlalchemy import select, func
        from app.models.user import User
        from app.models.campaign import Campaign
        from app.models.purchase_request import PurchaseRequest
        
        # 각 테이블의 데이터 수 조회
        user_count = await db.scalar(select(func.count(User.id)))
        campaign_count = await db.scalar(select(func.count(Campaign.id)))
        purchase_request_count = await db.scalar(select(func.count(PurchaseRequest.id)))
        
        # 슈퍼 어드민 수 조회
        superuser_count = await db.scalar(
            select(func.count(User.id)).where(User.role == UserRole.SUPER_ADMIN)
        )
        
        return {
            "system_status": "운영중",
            "database_counts": {
                "users": user_count,
                "superusers": superuser_count,
                "campaigns": campaign_count,
                "purchase_requests": purchase_request_count
            },
            "is_production_ready": user_count == superuser_count and campaign_count == 0 and purchase_request_count == 0
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시스템 상태 조회 중 오류가 발생했습니다: {str(e)}"
        )