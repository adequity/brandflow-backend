from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.models.campaign import Campaign
from app.models.campaign_cost import CampaignCost
from pydantic import BaseModel

router = APIRouter()


# Pydantic 스키마
class CampaignCostCreate(BaseModel):
    campaign_id: int
    cost_type: str
    description: Optional[str] = None
    amount: float
    receipt_url: Optional[str] = None
    vendor_name: Optional[str] = None


class CampaignCostResponse(BaseModel):
    id: int
    campaign_id: int
    cost_type: str
    description: Optional[str]
    amount: float
    receipt_url: Optional[str]
    vendor_name: Optional[str]
    is_approved: bool
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.post("/", response_model=CampaignCostResponse)
async def create_campaign_cost(
    cost_data: CampaignCostCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    캠페인 원가 항목 생성
    - STAFF, TEAM_LEADER만 생성 가능
    """
    # 권한 확인
    if current_user.role not in [UserRole.STAFF, UserRole.TEAM_LEADER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Permission denied")

    # 캠페인 존재 확인
    campaign_result = await db.execute(
        select(Campaign).where(Campaign.id == cost_data.campaign_id)
    )
    campaign = campaign_result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # 원가 항목 생성
    new_cost = CampaignCost(
        campaign_id=cost_data.campaign_id,
        cost_type=cost_data.cost_type,
        description=cost_data.description,
        amount=Decimal(str(cost_data.amount)),
        receipt_url=cost_data.receipt_url,
        vendor_name=cost_data.vendor_name,
        is_approved=False,
        created_by=current_user.id
    )

    db.add(new_cost)
    await db.commit()
    await db.refresh(new_cost)

    print(f"[CAMPAIGN-COST] Created cost {new_cost.id} for campaign {cost_data.campaign_id} by user {current_user.name}")

    return new_cost


@router.get("/campaign/{campaign_id}", response_model=List[CampaignCostResponse])
async def get_campaign_costs(
    campaign_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    특정 캠페인의 원가 항목 목록 조회
    """
    # 캠페인 존재 확인
    campaign_result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = campaign_result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # 원가 항목 조회
    result = await db.execute(
        select(CampaignCost).where(CampaignCost.campaign_id == campaign_id)
    )
    costs = result.scalars().all()

    return costs


@router.put("/{cost_id}/approve")
async def approve_campaign_cost(
    cost_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    원가 항목 승인
    - TEAM_LEADER, AGENCY_ADMIN, SUPER_ADMIN만 승인 가능
    """
    # 권한 확인
    if current_user.role not in [UserRole.TEAM_LEADER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Only team leaders and admins can approve costs")

    # 원가 항목 조회
    result = await db.execute(
        select(CampaignCost).where(CampaignCost.id == cost_id)
    )
    cost = result.scalar_one_or_none()

    if not cost:
        raise HTTPException(status_code=404, detail="Cost item not found")

    # 이미 승인된 경우
    if cost.is_approved:
        raise HTTPException(status_code=400, detail="Cost item already approved")

    # 승인 처리
    cost.is_approved = True
    cost.approved_by = current_user.id
    cost.approved_at = datetime.now()

    await db.commit()
    await db.refresh(cost)

    # 캠페인 원가 업데이트
    await _update_campaign_cost(db, cost.campaign_id)

    print(f"[CAMPAIGN-COST] Cost {cost_id} approved by {current_user.name}")

    return {"message": "Cost approved successfully", "cost_id": cost_id}


@router.delete("/{cost_id}")
async def delete_campaign_cost(
    cost_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    원가 항목 삭제
    - 생성자 본인 또는 TEAM_LEADER, ADMIN만 삭제 가능
    """
    # 원가 항목 조회
    result = await db.execute(
        select(CampaignCost).where(CampaignCost.id == cost_id)
    )
    cost = result.scalar_one_or_none()

    if not cost:
        raise HTTPException(status_code=404, detail="Cost item not found")

    # 권한 확인 (생성자 본인 또는 관리자)
    if cost.created_by != current_user.id and current_user.role not in [
        UserRole.TEAM_LEADER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN
    ]:
        raise HTTPException(status_code=403, detail="Permission denied")

    campaign_id = cost.campaign_id

    await db.delete(cost)
    await db.commit()

    # 캠페인 원가 업데이트
    await _update_campaign_cost(db, campaign_id)

    print(f"[CAMPAIGN-COST] Cost {cost_id} deleted by {current_user.name}")

    return {"message": "Cost deleted successfully", "cost_id": cost_id}


async def _update_campaign_cost(db: AsyncSession, campaign_id: int):
    """
    캠페인의 총 원가 및 이익 업데이트
    - 승인된 원가 항목만 합산
    """
    # 캠페인 조회
    campaign_result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = campaign_result.scalar_one_or_none()

    if not campaign:
        return

    # 승인된 원가 항목 합산
    costs_result = await db.execute(
        select(CampaignCost).where(
            CampaignCost.campaign_id == campaign_id,
            CampaignCost.is_approved == True
        )
    )
    costs = costs_result.scalars().all()

    total_cost = sum([Decimal(str(cost.amount)) for cost in costs])

    # 캠페인 원가 및 이익 업데이트 (취소된 캠페인은 마진 0)
    campaign.cost = total_cost
    if hasattr(campaign, 'status') and campaign.status and campaign.status.value == '취소':
        campaign.margin = Decimal('0')
        campaign.margin_rate = Decimal('0')
    else:
        effective_budget = Decimal(str(campaign.budget)) - Decimal(str(campaign.refund_amount or 0))
        campaign.margin = effective_budget - total_cost
        campaign.margin_rate = (campaign.margin / effective_budget * Decimal('100')) if effective_budget > 0 else Decimal('0')

    await db.commit()

    print(f"[CAMPAIGN-COST] Updated campaign {campaign_id} cost={total_cost}, margin={campaign.margin}")
