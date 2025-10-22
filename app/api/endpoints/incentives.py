from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, extract
from typing import List, Optional
from datetime import datetime

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.models.incentive import Incentive, IncentiveStatus
from app.models.incentive_rule import IncentiveRule
from app.services.incentive_service import IncentiveService

router = APIRouter()


@router.get("/my-incentive")
async def get_my_incentive(
    year: Optional[int] = Query(None, description="연도 (기본값: 현재 연도)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="월 (1-12, 기본값: 현재 월)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    본인의 월간 인센티브 조회
    - 년/월 미지정 시 현재 월 기준
    - 계산되지 않은 경우 자동 계산
    """
    # 기본값 설정
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    print(f"[INCENTIVE] User {current_user.name} requesting incentive for {year}-{month}")

    try:
        # 인센티브 계산 (없으면 생성, 있으면 재계산)
        incentive = await IncentiveService.calculate_monthly_incentive(
            db, current_user.id, year, month
        )

        return {
            "id": incentive.id,
            "user_id": incentive.user_id,
            "user_name": current_user.name,
            "year": incentive.year,
            "month": incentive.month,
            "personal": {
                "revenue": float(incentive.personal_revenue),
                "cost": float(incentive.personal_cost),
                "margin": float(incentive.personal_margin),
                "margin_rate": float(incentive.personal_margin_rate),
                "incentive_rate": float(incentive.personal_rate),
                "incentive": float(incentive.personal_incentive)
            },
            "team": {
                "revenue": float(incentive.team_revenue),
                "cost": float(incentive.team_cost),
                "margin": float(incentive.team_margin),
                "margin_rate": float(incentive.team_margin_rate),
                "incentive_rate": float(incentive.team_rate),
                "incentive": float(incentive.team_incentive)
            },
            "campaigns": {
                "total_count": incentive.campaign_count,
                "completed_count": incentive.completed_campaign_count,
                "completion_rate": float(incentive.completion_rate)
            },
            "bonus": float(incentive.bonus),
            "total_incentive": float(incentive.total_incentive),
            "status": incentive.status,
            "notes": incentive.notes
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"[INCENTIVE-ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate incentive: {str(e)}")


@router.get("/team-incentives")
async def get_team_incentives(
    year: Optional[int] = Query(None, description="연도 (기본값: 현재 연도)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="월 (1-12, 기본값: 현재 월)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    팀 전체 인센티브 조회 (TEAM_LEADER 전용)
    - 팀원들의 인센티브 목록 반환
    """
    # TEAM_LEADER 권한 확인
    if current_user.role != UserRole.TEAM_LEADER:
        raise HTTPException(status_code=403, detail="Only TEAM_LEADER can access team incentives")

    # 기본값 설정
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    print(f"[TEAM-INCENTIVE] Team Leader {current_user.name} requesting team incentives for {year}-{month}")

    try:
        # 팀원 조회 (같은 company + team_leader_id == 본인)
        team_members_result = await db.execute(
            select(User).where(
                and_(
                    User.company == current_user.company,
                    User.team_leader_id == current_user.id
                )
            )
        )
        team_members = team_members_result.scalars().all()

        if not team_members:
            return {
                "team_leader": current_user.name,
                "year": year,
                "month": month,
                "team_members": [],
                "summary": {
                    "total_revenue": 0,
                    "total_cost": 0,
                    "total_margin": 0,
                    "total_incentive": 0
                }
            }

        # 각 팀원의 인센티브 계산
        team_incentives = []
        total_revenue = 0.0
        total_cost = 0.0
        total_margin = 0.0
        total_incentive = 0.0

        for member in team_members:
            incentive = await IncentiveService.calculate_monthly_incentive(
                db, member.id, year, month
            )

            member_data = {
                "user_id": member.id,
                "user_name": member.name,
                "revenue": float(incentive.personal_revenue),
                "cost": float(incentive.personal_cost),
                "margin": float(incentive.personal_margin),
                "margin_rate": float(incentive.personal_margin_rate),
                "incentive": float(incentive.personal_incentive),
                "bonus": float(incentive.bonus),
                "total_incentive": float(incentive.total_incentive),
                "campaign_count": incentive.campaign_count,
                "completed_count": incentive.completed_campaign_count,
                "completion_rate": float(incentive.completion_rate)
            }

            team_incentives.append(member_data)

            total_revenue += float(incentive.personal_revenue)
            total_cost += float(incentive.personal_cost)
            total_margin += float(incentive.personal_margin)
            total_incentive += float(incentive.total_incentive)

        return {
            "team_leader": current_user.name,
            "year": year,
            "month": month,
            "team_members": team_incentives,
            "summary": {
                "total_revenue": total_revenue,
                "total_cost": total_cost,
                "total_margin": total_margin,
                "total_incentive": total_incentive,
                "member_count": len(team_members)
            }
        }
    except Exception as e:
        print(f"[TEAM-INCENTIVE-ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get team incentives: {str(e)}")


@router.get("/rules")
async def get_incentive_rules(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    인센티브 정책 규칙 조회
    - 모든 역할의 인센티브 정책 반환
    """
    # ADMIN 권한 확인 (SUPER_ADMIN 또는 AGENCY_ADMIN만 조회 가능)
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can access incentive rules")

    result = await db.execute(
        select(IncentiveRule).where(IncentiveRule.is_active == True)
    )
    rules = result.scalars().all()

    return {
        "rules": [
            {
                "id": rule.id,
                "role": rule.role,
                "personal_rate": float(rule.personal_rate),
                "team_rate": float(rule.team_rate),
                "company_rate": float(rule.company_rate),
                "bonus_threshold_margin": float(rule.bonus_threshold_margin) if rule.bonus_threshold_margin else None,
                "bonus_amount": float(rule.bonus_amount) if rule.bonus_amount else None,
                "bonus_completion_rate": float(rule.bonus_completion_rate) if rule.bonus_completion_rate else None,
                "is_active": rule.is_active,
                "effective_from": rule.effective_from.isoformat() if rule.effective_from else None
            }
            for rule in rules
        ]
    }
