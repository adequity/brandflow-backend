from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, extract, desc, func, select
from typing import List, Optional
import logging
from datetime import datetime

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.models.monthly_incentive import MonthlyIncentive, IncentiveStatus
from app.models.campaign import Campaign, CampaignStatus
from app.models.post import Post
from app.schemas.monthly_incentive import (
    MonthlyIncentiveResponse,
    MonthlyIncentiveUpdate,
    IncentiveCalculationRequest,
    IncentiveCalculationResponse,
    IncentiveCalculationResult,
    IncentiveStatsResponse,
    IncentiveListQuery
)

# 로거 설정
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
async def health_check():
    """월간 인센티브 시스템 헬스 체크"""
    return {
        "status": "healthy",
        "message": "월간 인센티브 시스템이 정상 작동 중입니다",
        "timestamp": datetime.now().isoformat()
    }

@router.post("/calculate", response_model=IncentiveCalculationResponse)
async def calculate_monthly_incentives(
    request: IncentiveCalculationRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """월간 인센티브 계산"""

    # 권한 확인
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다")

    # 임시 응답 - 실제 계산 로직은 추후 구현
    return IncentiveCalculationResponse(
        success=True,
        total_processed=0,
        results=[],
        summary={"created": 0, "updated": 0, "skipped": 0, "error": 0}
    )

@router.get("/", response_model=List[MonthlyIncentiveResponse])
async def get_monthly_incentives(
    year: Optional[int] = Query(None, description="연도"),
    month: Optional[int] = Query(None, description="월"),
    company: Optional[str] = Query(None, description="회사명"),
    status: Optional[IncentiveStatus] = Query(None, description="상태"),
    user_id: Optional[int] = Query(None, description="사용자 ID"),
    limit: int = Query(100, ge=1, le=1000, description="조회 제한"),
    offset: int = Query(0, ge=0, description="조회 오프셋"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """월간 인센티브 목록 조회"""

    # 권한 확인
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다")

    # 임시 빈 리스트 반환 - 실제 조회 로직은 추후 구현
    return []

@router.get("/stats", response_model=IncentiveStatsResponse)
async def get_incentive_stats(
    year: Optional[int] = Query(None, description="연도"),
    month: Optional[int] = Query(None, description="월"),
    company: Optional[str] = Query(None, description="회사명"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """월간 인센티브 통계 조회"""

    # 권한 확인
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다")

    # 임시 기본 통계 반환 - 실제 통계 로직은 추후 구현
    return IncentiveStatsResponse(
        total_employees=0,
        pending_incentives=0,
        approved_incentives=0,
        paid_incentives=0,
        total_incentive_amount=0.0,
        total_adjustment_amount=0.0,
        total_bonus_amount=0.0,
        total_final_amount=0.0,
        companies=[]
    )

@router.put("/{incentive_id}", response_model=MonthlyIncentiveResponse)
async def update_monthly_incentive(
    incentive_id: int,
    update_data: MonthlyIncentiveUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """월간 인센티브 수정"""

    # 권한 확인
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다")

    raise HTTPException(status_code=501, detail="아직 구현되지 않은 기능입니다")

@router.delete("/{incentive_id}")
async def delete_monthly_incentive(
    incentive_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """월간 인센티브 삭제"""

    # 권한 확인
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다")

    raise HTTPException(status_code=501, detail="아직 구현되지 않은 기능입니다")