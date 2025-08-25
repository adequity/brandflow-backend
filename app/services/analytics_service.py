"""
Analytics service for BrandFlow API
데이터 분석 및 대시보드 서비스
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, extract, case, desc, asc
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import calendar

from app.models.user import User, UserRole
from app.models.campaign import Campaign, CampaignStatus
from app.models.purchase_request import PurchaseRequest, RequestStatus
from app.core.cache import cached
from app.core.logging import security_logger


class AnalyticsService:
    """분석 및 대시보드 데이터 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_dashboard_stats(
        self, 
        user: User, 
        date_from: Optional[datetime] = None, 
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """권한별 대시보드 통계 조회"""
        
        # 기본 날짜 설정 (최근 30일)
        if not date_to:
            date_to = datetime.now()
        if not date_from:
            date_from = date_to - timedelta(days=30)
        
        if user.role == UserRole.SUPER_ADMIN:
            return await self._get_super_admin_stats(date_from, date_to)
        elif user.role == UserRole.AGENCY_ADMIN:
            return await self._get_agency_admin_stats(user, date_from, date_to)
        elif user.role == UserRole.CLIENT:
            return await self._get_client_stats(user, date_from, date_to)
        else:  # STAFF
            return await self._get_staff_stats(user, date_from, date_to)
    
    async def _get_super_admin_stats(
        self, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """슈퍼 어드민 전체 통계"""
        
        # 캠페인 통계
        total_campaigns = await self._count_campaigns()
        active_campaigns = await self._count_campaigns(status=CampaignStatus.ACTIVE)
        completed_campaigns = await self._count_campaigns(status=CampaignStatus.COMPLETED)
        
        # 사용자 통계
        total_users = await self._count_users()
        active_users = await self._count_users(active_only=True)
        
        # 구매요청 통계
        total_requests = await self._count_purchase_requests()
        pending_requests = await self._count_purchase_requests(status=RequestStatus.PENDING)
        approved_requests = await self._count_purchase_requests(status=RequestStatus.APPROVED)
        
        # 비용 통계
        total_expenses = await self._calculate_total_expenses()
        monthly_expenses = await self._calculate_monthly_expenses(date_from, date_to)
        
        # 성과 지표
        conversion_rate = await self._calculate_conversion_rate()
        average_campaign_budget = await self._calculate_average_campaign_budget()
        
        # 최근 활동
        recent_activities = await self._get_recent_activities(limit=10)
        
        return {
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "completed_campaigns": completed_campaigns,
            "total_users": total_users,
            "active_users": active_users,
            "total_expenses": total_expenses,
            "monthly_expenses": monthly_expenses,
            "total_requests": total_requests,
            "pending_requests": pending_requests,
            "approved_requests": approved_requests,
            "conversion_rate": conversion_rate,
            "average_campaign_budget": average_campaign_budget,
            "recent_activities": recent_activities,
            "date_range": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat()
            }
        }
    
    async def _get_agency_admin_stats(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """대행사 어드민 회사별 통계"""
        
        # 회사 필터링 조건
        company_filter = User.company == user.company
        
        # 캠페인 통계 (회사별)
        total_campaigns = await self._count_campaigns(company_filter=company_filter)
        active_campaigns = await self._count_campaigns(
            status=CampaignStatus.ACTIVE, 
            company_filter=company_filter
        )
        
        # 회사 사용자 통계
        company_users = await self._count_users(company_filter=company_filter)
        active_company_users = await self._count_users(
            active_only=True, 
            company_filter=company_filter
        )
        
        # 회사 구매요청 통계
        company_requests = await self._count_purchase_requests(company_filter=company_filter)
        
        # 회사 비용 통계
        company_expenses = await self._calculate_total_expenses(company_filter=company_filter)
        
        # 최근 활동 (회사별)
        recent_activities = await self._get_recent_activities(
            limit=10, 
            company_filter=company_filter
        )
        
        return {
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "total_users": company_users,
            "active_users": active_company_users,
            "total_expenses": company_expenses,
            "monthly_expenses": 0,  # TODO: 월별 계산 추가
            "total_requests": company_requests,
            "recent_activities": recent_activities,
            "company": user.company
        }
    
    async def _get_client_stats(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """클라이언트 개인 통계"""
        
        # 개인 캠페인 통계
        user_campaigns = await self._count_campaigns(creator_id=user.id)
        active_campaigns = await self._count_campaigns(
            creator_id=user.id, 
            status=CampaignStatus.ACTIVE
        )
        
        # 개인 구매요청 통계
        user_requests = await self._count_purchase_requests(requester_id=user.id)
        pending_requests = await self._count_purchase_requests(
            requester_id=user.id, 
            status=RequestStatus.PENDING
        )
        
        # 개인 비용 통계
        user_expenses = await self._calculate_total_expenses(creator_id=user.id)
        
        # 최근 활동 (개인)
        recent_activities = await self._get_recent_activities(
            limit=5, 
            creator_id=user.id
        )
        
        return {
            "total_campaigns": user_campaigns,
            "active_campaigns": active_campaigns,
            "total_expenses": user_expenses,
            "monthly_expenses": 0,
            "total_requests": user_requests,
            "pending_requests": pending_requests,
            "recent_activities": recent_activities,
            "user_id": user.id
        }
    
    async def _get_staff_stats(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """직원 기본 통계"""
        
        # 회사 기본 정보만 제공
        company_users = await self._count_users(
            company_filter=(User.company == user.company)
        )
        
        return {
            "total_campaigns": 0,
            "active_campaigns": 0,
            "total_expenses": 0,
            "monthly_expenses": 0,
            "total_users": company_users,
            "recent_activities": [],
            "access_level": "staff"
        }
    
    # 기본 통계 메서드들
    async def _count_campaigns(
        self, 
        status: Optional[CampaignStatus] = None,
        company_filter: Optional[Any] = None,
        creator_id: Optional[int] = None
    ) -> int:
        """캠페인 개수 조회"""
        query = select(func.count(Campaign.id))
        
        conditions = []
        if status:
            conditions.append(Campaign.status == status)
        
        if creator_id:
            conditions.append(Campaign.creator_id == creator_id)
        
        if company_filter is not None:
            query = query.join(User, Campaign.creator_id == User.id)
            conditions.append(company_filter)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _count_users(
        self, 
        active_only: bool = False,
        company_filter: Optional[Any] = None
    ) -> int:
        """사용자 개수 조회"""
        query = select(func.count(User.id))
        
        conditions = []
        if active_only:
            conditions.append(User.is_active == True)
        
        if company_filter is not None:
            conditions.append(company_filter)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _count_purchase_requests(
        self, 
        status: Optional[RequestStatus] = None,
        company_filter: Optional[Any] = None,
        requester_id: Optional[int] = None
    ) -> int:
        """구매요청 개수 조회"""
        query = select(func.count(PurchaseRequest.id))
        
        conditions = []
        if status:
            conditions.append(PurchaseRequest.status == status)
        
        if requester_id:
            conditions.append(PurchaseRequest.requester_id == requester_id)
        
        if company_filter is not None:
            query = query.join(User, PurchaseRequest.requester_id == User.id)
            conditions.append(company_filter)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _calculate_total_expenses(
        self, 
        company_filter: Optional[Any] = None,
        creator_id: Optional[int] = None
    ) -> float:
        """총 비용 계산"""
        # 캠페인 예산 합계
        campaign_query = select(func.sum(Campaign.budget))
        
        # 구매요청 비용 합계
        request_query = select(func.sum(PurchaseRequest.amount))
        
        conditions_campaign = []
        conditions_request = []
        
        if creator_id:
            conditions_campaign.append(Campaign.creator_id == creator_id)
            conditions_request.append(PurchaseRequest.requester_id == creator_id)
        
        if company_filter is not None:
            campaign_query = campaign_query.join(User, Campaign.creator_id == User.id)
            request_query = request_query.join(User, PurchaseRequest.requester_id == User.id)
            conditions_campaign.append(company_filter)
            conditions_request.append(company_filter)
        
        if conditions_campaign:
            campaign_query = campaign_query.where(and_(*conditions_campaign))
        
        if conditions_request:
            request_query = request_query.where(and_(*conditions_request))
        
        # 캠페인 예산 합계
        campaign_result = await self.db.execute(campaign_query)
        campaign_total = campaign_result.scalar() or 0.0
        
        # 구매요청 비용 합계
        request_result = await self.db.execute(request_query)
        request_total = request_result.scalar() or 0.0
        
        return float(campaign_total + request_total)
    
    async def _calculate_monthly_expenses(
        self, 
        date_from: datetime, 
        date_to: datetime
    ) -> List[Dict[str, Any]]:
        """월별 비용 계산"""
        # 월별 캠페인 예산 집계
        monthly_query = select(
            extract('year', Campaign.created_at).label('year'),
            extract('month', Campaign.created_at).label('month'),
            func.sum(Campaign.budget).label('total_budget')
        ).where(
            and_(
                Campaign.created_at >= date_from,
                Campaign.created_at <= date_to
            )
        ).group_by(
            extract('year', Campaign.created_at),
            extract('month', Campaign.created_at)
        ).order_by(
            extract('year', Campaign.created_at),
            extract('month', Campaign.created_at)
        )
        
        result = await self.db.execute(monthly_query)
        monthly_data = []
        
        for row in result:
            month_name = calendar.month_name[int(row.month)]
            monthly_data.append({
                "year": int(row.year),
                "month": int(row.month),
                "month_name": month_name,
                "total_expenses": float(row.total_budget or 0.0)
            })
        
        return monthly_data
    
    async def _calculate_conversion_rate(self) -> float:
        """전환율 계산 (완료된 캠페인 / 전체 캠페인)"""
        total = await self._count_campaigns()
        completed = await self._count_campaigns(status=CampaignStatus.COMPLETED)
        
        if total == 0:
            return 0.0
        
        return round((completed / total) * 100, 2)
    
    async def _calculate_average_campaign_budget(self) -> float:
        """평균 캠페인 예산 계산"""
        query = select(func.avg(Campaign.budget))
        result = await self.db.execute(query)
        avg_budget = result.scalar()
        
        return float(avg_budget or 0.0)
    
    async def _get_recent_activities(
        self, 
        limit: int = 10,
        company_filter: Optional[Any] = None,
        creator_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """최근 활동 조회"""
        activities = []
        
        # 최근 캠페인 활동
        campaign_query = select(
            Campaign.id,
            Campaign.name,
            Campaign.status,
            Campaign.created_at,
            User.name.label('creator_name')
        ).join(
            User, Campaign.creator_id == User.id
        ).order_by(
            desc(Campaign.created_at)
        ).limit(limit // 2)
        
        # 최근 구매요청 활동
        request_query = select(
            PurchaseRequest.id,
            PurchaseRequest.title,
            PurchaseRequest.status,
            PurchaseRequest.amount,
            PurchaseRequest.created_at,
            User.name.label('requester_name')
        ).join(
            User, PurchaseRequest.requester_id == User.id
        ).order_by(
            desc(PurchaseRequest.created_at)
        ).limit(limit // 2)
        
        # 필터 적용
        conditions_campaign = []
        conditions_request = []
        
        if creator_id:
            conditions_campaign.append(Campaign.creator_id == creator_id)
            conditions_request.append(PurchaseRequest.requester_id == creator_id)
        
        if company_filter is not None:
            conditions_campaign.append(company_filter)
            conditions_request.append(company_filter)
        
        if conditions_campaign:
            campaign_query = campaign_query.where(and_(*conditions_campaign))
        
        if conditions_request:
            request_query = request_query.where(and_(*conditions_request))
        
        # 캠페인 활동 조회
        campaign_result = await self.db.execute(campaign_query)
        for row in campaign_result:
            activities.append({
                "type": "campaign",
                "id": row.id,
                "title": row.name,
                "status": row.status.value if row.status else None,
                "actor": row.creator_name,
                "timestamp": row.created_at.isoformat(),
                "description": f"캠페인 '{row.name}' 생성됨"
            })
        
        # 구매요청 활동 조회
        request_result = await self.db.execute(request_query)
        for row in request_result:
            activities.append({
                "type": "purchase_request",
                "id": row.id,
                "title": row.title,
                "status": row.status.value if row.status else None,
                "amount": float(row.amount),
                "actor": row.requester_name,
                "timestamp": row.created_at.isoformat(),
                "description": f"구매요청 '{row.title}' 생성됨"
            })
        
        # 시간순 정렬
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return activities[:limit]