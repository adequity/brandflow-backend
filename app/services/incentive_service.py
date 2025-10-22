from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, extract
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional

from app.models.user import User, UserRole
from app.models.campaign import Campaign, CampaignStatus
from app.models.incentive import Incentive, IncentiveStatus
from app.models.incentive_rule import IncentiveRule


class IncentiveService:
    """인센티브 계산 및 관리 서비스"""

    @staticmethod
    async def calculate_monthly_incentive(
        db: AsyncSession,
        user_id: int,
        year: int,
        month: int
    ) -> Incentive:
        """
        특정 사용자의 월간 인센티브 계산

        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            year: 연도
            month: 월

        Returns:
            Incentive: 계산된 인센티브 객체
        """
        # 사용자 조회
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User {user_id} not found")

        # 해당 역할의 인센티브 정책 조회
        rule_result = await db.execute(
            select(IncentiveRule).where(
                and_(
                    IncentiveRule.role == user.role.value,
                    IncentiveRule.is_active == True
                )
            )
        )
        rule = rule_result.scalar_one_or_none()

        if not rule:
            # 기본 정책 사용
            rule = IncentiveRule(
                role=user.role.value,
                personal_rate=Decimal('10.0'),
                team_rate=Decimal('15.0'),
                company_rate=Decimal('5.0')
            )

        # 기존 인센티브 레코드 조회 (있으면 업데이트, 없으면 생성)
        existing_result = await db.execute(
            select(Incentive).where(
                and_(
                    Incentive.user_id == user_id,
                    Incentive.year == year,
                    Incentive.month == month
                )
            )
        )
        incentive = existing_result.scalar_one_or_none()

        if not incentive:
            incentive = Incentive(
                user_id=user_id,
                year=year,
                month=month
            )
            db.add(incentive)

        # 본인 담당 캠페인 데이터 집계
        personal_campaigns = await IncentiveService._get_user_campaigns(
            db, user_id, year, month
        )

        incentive.personal_revenue = personal_campaigns['revenue']
        incentive.personal_cost = personal_campaigns['cost']
        incentive.personal_margin = personal_campaigns['margin']
        incentive.personal_margin_rate = personal_campaigns['margin_rate']
        incentive.campaign_count = personal_campaigns['count']
        incentive.completed_campaign_count = personal_campaigns['completed_count']
        incentive.completion_rate = personal_campaigns['completion_rate']

        # 본인 인센티브 계산 (이익 기준)
        incentive.personal_rate = rule.personal_rate
        incentive.personal_incentive = (incentive.personal_margin * rule.personal_rate / Decimal('100'))

        # TEAM_LEADER인 경우 팀 인센티브 계산
        if user.role == UserRole.TEAM_LEADER:
            team_campaigns = await IncentiveService._get_team_campaigns(
                db, user_id, year, month
            )

            incentive.team_revenue = team_campaigns['revenue']
            incentive.team_cost = team_campaigns['cost']
            incentive.team_margin = team_campaigns['margin']
            incentive.team_margin_rate = team_campaigns['margin_rate']
            incentive.team_rate = rule.team_rate
            incentive.team_incentive = (incentive.team_margin * rule.team_rate / Decimal('100'))
        else:
            incentive.team_revenue = Decimal('0')
            incentive.team_cost = Decimal('0')
            incentive.team_margin = Decimal('0')
            incentive.team_margin_rate = Decimal('0')
            incentive.team_rate = Decimal('0')
            incentive.team_incentive = Decimal('0')

        # AGENCY_ADMIN인 경우 회사 인센티브 계산
        if user.role == UserRole.AGENCY_ADMIN:
            company_campaigns = await IncentiveService._get_company_campaigns(
                db, user.company, year, month
            )

            incentive.company_revenue = company_campaigns['revenue']
            incentive.company_cost = company_campaigns['cost']
            incentive.company_margin = company_campaigns['margin']
            incentive.company_margin_rate = company_campaigns['margin_rate']
            incentive.company_incentive = (incentive.company_margin * rule.company_rate / Decimal('100'))
        else:
            incentive.company_revenue = Decimal('0')
            incentive.company_cost = Decimal('0')
            incentive.company_margin = Decimal('0')
            incentive.company_margin_rate = Decimal('0')

        # 성과 보너스 계산
        incentive.bonus = Decimal('0')
        if rule.bonus_threshold_margin and rule.bonus_amount and rule.bonus_completion_rate:
            # 이익 기준 충족 AND 완료율 기준 충족
            if (incentive.personal_margin >= rule.bonus_threshold_margin and
                incentive.completion_rate >= rule.bonus_completion_rate):
                incentive.bonus = rule.bonus_amount

        # 총 인센티브 계산
        incentive.total_incentive = (
            incentive.personal_incentive +
            incentive.team_incentive +
            incentive.bonus
        )

        await db.commit()
        await db.refresh(incentive)

        return incentive

    @staticmethod
    async def _get_user_campaigns(db: AsyncSession, user_id: int, year: int, month: int) -> dict:
        """사용자의 월간 캠페인 데이터 집계"""
        # 해당 월의 캠페인 조회 (creator_id 또는 staff_id 기준)
        query = select(Campaign).where(
            and_(
                extract('year', Campaign.start_date) == year,
                extract('month', Campaign.start_date) == month,
                func.or_(
                    Campaign.creator_id == user_id,
                    Campaign.staff_id == user_id
                )
            )
        )

        result = await db.execute(query)
        campaigns = result.scalars().all()

        total_revenue = Decimal('0')
        total_cost = Decimal('0')
        completed_count = 0

        for campaign in campaigns:
            total_revenue += Decimal(str(campaign.budget))
            total_cost += Decimal(str(campaign.cost or 0))
            if campaign.status == CampaignStatus.COMPLETED:
                completed_count += 1

        total_margin = total_revenue - total_cost
        margin_rate = (total_margin / total_revenue * Decimal('100')) if total_revenue > 0 else Decimal('0')
        completion_rate = (Decimal(str(completed_count)) / Decimal(str(len(campaigns))) * Decimal('100')) if len(campaigns) > 0 else Decimal('0')

        return {
            'revenue': total_revenue,
            'cost': total_cost,
            'margin': total_margin,
            'margin_rate': margin_rate,
            'count': len(campaigns),
            'completed_count': completed_count,
            'completion_rate': completion_rate
        }

    @staticmethod
    async def _get_team_campaigns(db: AsyncSession, team_leader_id: int, year: int, month: int) -> dict:
        """팀장의 팀 전체 월간 캠페인 데이터 집계"""
        # 팀장 정보 조회
        leader_result = await db.execute(
            select(User).where(User.id == team_leader_id)
        )
        leader = leader_result.scalar_one_or_none()

        if not leader:
            return {
                'revenue': Decimal('0'),
                'cost': Decimal('0'),
                'margin': Decimal('0'),
                'margin_rate': Decimal('0')
            }

        # 팀원 ID 조회 (같은 company + team_leader_id == 본인)
        team_members_result = await db.execute(
            select(User.id).where(
                and_(
                    User.company == leader.company,
                    User.team_leader_id == team_leader_id
                )
            )
        )
        team_member_ids = [row[0] for row in team_members_result.all()]

        if not team_member_ids:
            return {
                'revenue': Decimal('0'),
                'cost': Decimal('0'),
                'margin': Decimal('0'),
                'margin_rate': Decimal('0')
            }

        # 팀원들의 캠페인 조회
        query = select(Campaign).where(
            and_(
                extract('year', Campaign.start_date) == year,
                extract('month', Campaign.start_date) == month,
                func.or_(
                    Campaign.creator_id.in_(team_member_ids),
                    Campaign.staff_id.in_(team_member_ids)
                )
            )
        )

        result = await db.execute(query)
        campaigns = result.scalars().all()

        total_revenue = Decimal('0')
        total_cost = Decimal('0')

        for campaign in campaigns:
            total_revenue += Decimal(str(campaign.budget))
            total_cost += Decimal(str(campaign.cost or 0))

        total_margin = total_revenue - total_cost
        margin_rate = (total_margin / total_revenue * Decimal('100')) if total_revenue > 0 else Decimal('0')

        return {
            'revenue': total_revenue,
            'cost': total_cost,
            'margin': total_margin,
            'margin_rate': margin_rate
        }

    @staticmethod
    async def _get_company_campaigns(db: AsyncSession, company: str, year: int, month: int) -> dict:
        """회사 전체 월간 캠페인 데이터 집계"""
        # 회사의 모든 캠페인 조회 (campaign.company 기준)
        query = select(Campaign).where(
            and_(
                extract('year', Campaign.start_date) == year,
                extract('month', Campaign.start_date) == month,
                Campaign.company == company
            )
        )

        result = await db.execute(query)
        campaigns = result.scalars().all()

        total_revenue = Decimal('0')
        total_cost = Decimal('0')

        for campaign in campaigns:
            total_revenue += Decimal(str(campaign.budget))
            total_cost += Decimal(str(campaign.cost or 0))

        total_margin = total_revenue - total_cost
        margin_rate = (total_margin / total_revenue * Decimal('100')) if total_revenue > 0 else Decimal('0')

        return {
            'revenue': total_revenue,
            'cost': total_cost,
            'margin': total_margin,
            'margin_rate': margin_rate
        }
