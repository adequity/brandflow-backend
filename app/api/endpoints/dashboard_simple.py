from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.models.campaign import Campaign
from app.models.purchase_request import PurchaseRequest

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """간단한 대시보드 통계 데이터 조회"""
    
    try:
        # 사용자 역할에 따른 기본 통계
        if current_user.role == UserRole.SUPER_ADMIN:
            # 슈퍼 어드민 - 전체 데이터
            total_campaigns_result = await db.execute(select(func.count(Campaign.id)))
            total_campaigns = total_campaigns_result.scalar() or 0
            
            total_users_result = await db.execute(select(func.count(User.id)))
            total_users = total_users_result.scalar() or 0
            
        elif current_user.role == UserRole.AGENCY_ADMIN:
            # 대행사 어드민 - 회사 데이터
            if current_user.company:
                company_campaigns_result = await db.execute(
                    select(func.count(Campaign.id))
                    .join(User, Campaign.creator_id == User.id)
                    .where(User.company == current_user.company)
                )
                total_campaigns = company_campaigns_result.scalar() or 0
                
                company_users_result = await db.execute(
                    select(func.count(User.id)).where(User.company == current_user.company)
                )
                total_users = company_users_result.scalar() or 0
            else:
                total_campaigns = 0
                total_users = 1
                
        elif current_user.role == UserRole.CLIENT:
            # 클라이언트 - 개인 데이터
            user_campaigns_result = await db.execute(
                select(func.count(Campaign.id)).where(Campaign.creator_id == current_user.id)
            )
            total_campaigns = user_campaigns_result.scalar() or 0
            total_users = 1
            
        else:
            # 직원 - 최소 데이터
            total_campaigns = 0
            total_users = 1

        return {
            "total_campaigns": total_campaigns,
            "active_campaigns": 0,  # TODO: 활성 캠페인 계산
            "total_expenses": 0.0,  # TODO: 비용 계산
            "monthly_expenses": 0.0,  # TODO: 월별 비용 계산
            "total_users": total_users,
            "recent_activities": [],  # TODO: 최근 활동
            "user_role": current_user.role.value,
            "user_name": current_user.name,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        }
        
    except Exception as e:
        return {
            "total_campaigns": 0,
            "active_campaigns": 0,
            "total_expenses": 0.0,
            "monthly_expenses": 0.0,
            "total_users": 0,
            "recent_activities": [],
            "user_role": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "status": "error"
        }


@router.get("/health")
async def dashboard_health():
    """대시보드 헬스체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "dashboard"
    }