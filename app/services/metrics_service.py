"""
Real-time metrics service for BrandFlow API
실시간 통계 및 메트릭 시스템
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import time
import asyncio

from app.models.user import User, UserRole
from app.models.campaign import Campaign, CampaignStatus
from app.models.purchase_request import PurchaseRequest, RequestStatus
from app.core.cache import app_cache


class MetricsService:
    """실시간 메트릭 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_real_time_metrics(self, user: User) -> Dict[str, Any]:
        """실시간 메트릭 조회"""
        
        # 캐시에서 기존 메트릭 조회
        cache_key = f"metrics_{user.id}_{user.role.value}"
        cached_metrics = await app_cache.get(cache_key)
        
        if cached_metrics:
            # 캐시된 데이터에 실시간 업데이트 추가
            cached_metrics["last_updated"] = datetime.now().isoformat()
            return cached_metrics
        
        # 새로운 메트릭 계산
        metrics = await self._calculate_fresh_metrics(user)
        
        # 캐시에 저장 (30초 TTL)
        await app_cache.set(cache_key, metrics, ttl=30)
        
        return metrics
    
    async def _calculate_fresh_metrics(self, user: User) -> Dict[str, Any]:
        """새로운 메트릭 계산"""
        
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start = today_start - timedelta(days=7)
        
        metrics = {
            "timestamp": now.isoformat(),
            "user_info": {
                "id": user.id,
                "name": user.name,
                "role": user.role.value,
                "company": user.company
            }
        }
        
        if user.role == UserRole.SUPER_ADMIN:
            metrics.update(await self._get_super_admin_metrics(today_start, yesterday_start, week_start))
        elif user.role == UserRole.AGENCY_ADMIN:
            metrics.update(await self._get_agency_metrics(user, today_start, yesterday_start, week_start))
        elif user.role == UserRole.CLIENT:
            metrics.update(await self._get_client_metrics(user, today_start, yesterday_start, week_start))
        else:  # STAFF
            metrics.update(await self._get_staff_metrics(user))
        
        return metrics
    
    async def _get_super_admin_metrics(
        self, 
        today_start: datetime, 
        yesterday_start: datetime, 
        week_start: datetime
    ) -> Dict[str, Any]:
        """슈퍼 어드민 실시간 메트릭"""
        
        # 오늘의 신규 항목들
        today_campaigns = await self._count_items_since(Campaign, today_start)
        today_users = await self._count_items_since(User, today_start)
        today_requests = await self._count_items_since(PurchaseRequest, today_start)
        
        # 어제와 비교
        yesterday_campaigns = await self._count_items_between(
            Campaign, yesterday_start, today_start
        )
        yesterday_users = await self._count_items_between(
            User, yesterday_start, today_start
        )
        yesterday_requests = await self._count_items_between(
            PurchaseRequest, yesterday_start, today_start
        )
        
        # 이번 주 통계
        week_campaigns = await self._count_items_since(Campaign, week_start)
        week_revenue = await self._calculate_revenue_since(week_start)
        
        # 활성 상태 통계
        active_campaigns = await self._count_active_campaigns()
        pending_requests = await self._count_pending_requests()
        
        # 성장률 계산
        campaign_growth = self._calculate_growth_rate(today_campaigns, yesterday_campaigns)
        user_growth = self._calculate_growth_rate(today_users, yesterday_users)
        
        return {
            "today": {
                "new_campaigns": today_campaigns,
                "new_users": today_users,
                "new_requests": today_requests,
                "campaign_growth_rate": campaign_growth,
                "user_growth_rate": user_growth
            },
            "week": {
                "total_campaigns": week_campaigns,
                "total_revenue": week_revenue,
                "avg_daily_campaigns": week_campaigns / 7
            },
            "current": {
                "active_campaigns": active_campaigns,
                "pending_requests": pending_requests,
                "system_status": "operational"
            },
            "performance": await self._get_system_performance_metrics()
        }
    
    async def _get_agency_metrics(
        self, 
        user: User, 
        today_start: datetime, 
        yesterday_start: datetime, 
        week_start: datetime
    ) -> Dict[str, Any]:
        """대행사 어드민 메트릭"""
        
        company_filter = User.company == user.company
        
        # 회사 캠페인 통계
        company_campaigns_today = await self._count_campaigns_with_filter(
            today_start, None, company_filter
        )
        company_campaigns_week = await self._count_campaigns_with_filter(
            week_start, None, company_filter
        )
        
        # 회사 사용자 통계
        company_users = await self._count_company_users(user.company)
        active_company_users = await self._count_company_users(user.company, active_only=True)
        
        # 회사 수익 통계
        company_revenue = await self._calculate_company_revenue(user.company, week_start)
        
        return {
            "today": {
                "company_campaigns": company_campaigns_today,
                "company_name": user.company
            },
            "week": {
                "total_campaigns": company_campaigns_week,
                "company_revenue": company_revenue,
                "avg_daily_campaigns": company_campaigns_week / 7
            },
            "team": {
                "total_users": company_users,
                "active_users": active_company_users,
                "utilization_rate": (active_company_users / company_users * 100) if company_users > 0 else 0
            }
        }
    
    async def _get_client_metrics(
        self, 
        user: User, 
        today_start: datetime, 
        yesterday_start: datetime, 
        week_start: datetime
    ) -> Dict[str, Any]:
        """클라이언트 개인 메트릭"""
        
        # 개인 캠페인 통계
        user_campaigns_today = await self._count_campaigns_with_filter(
            today_start, None, None, user.id
        )
        user_campaigns_week = await self._count_campaigns_with_filter(
            week_start, None, None, user.id
        )
        
        # 개인 구매요청 통계
        user_requests_today = await self._count_requests_with_filter(
            today_start, None, None, user.id
        )
        user_pending_requests = await self._count_user_pending_requests(user.id)
        
        # 개인 지출 통계
        user_spending_week = await self._calculate_user_spending(user.id, week_start)
        
        return {
            "today": {
                "new_campaigns": user_campaigns_today,
                "new_requests": user_requests_today
            },
            "week": {
                "total_campaigns": user_campaigns_week,
                "total_spending": user_spending_week,
                "avg_daily_campaigns": user_campaigns_week / 7
            },
            "pending": {
                "requests": user_pending_requests,
                "status": "active" if user.is_active else "inactive"
            }
        }
    
    async def _get_staff_metrics(self, user: User) -> Dict[str, Any]:
        """직원 기본 메트릭"""
        
        return {
            "access_level": "staff",
            "company": user.company,
            "status": "active" if user.is_active else "inactive",
            "limited_access": True
        }
    
    # 헬퍼 메서드들
    async def _count_items_since(self, model, since: datetime) -> int:
        """특정 시간 이후 생성된 항목 개수"""
        query = select(func.count(model.id)).where(model.created_at >= since)
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _count_items_between(self, model, start: datetime, end: datetime) -> int:
        """특정 기간 사이 생성된 항목 개수"""
        query = select(func.count(model.id)).where(
            and_(model.created_at >= start, model.created_at < end)
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _count_campaigns_with_filter(
        self, 
        start: Optional[datetime] = None, 
        end: Optional[datetime] = None,
        company_filter: Optional[Any] = None,
        creator_id: Optional[int] = None
    ) -> int:
        """필터링된 캠페인 개수"""
        query = select(func.count(Campaign.id))
        
        conditions = []
        if start:
            conditions.append(Campaign.created_at >= start)
        if end:
            conditions.append(Campaign.created_at < end)
        if creator_id:
            conditions.append(Campaign.creator_id == creator_id)
        
        if company_filter is not None:
            query = query.join(User, Campaign.creator_id == User.id)
            conditions.append(company_filter)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _count_requests_with_filter(
        self, 
        start: Optional[datetime] = None, 
        end: Optional[datetime] = None,
        company_filter: Optional[Any] = None,
        requester_id: Optional[int] = None
    ) -> int:
        """필터링된 구매요청 개수"""
        query = select(func.count(PurchaseRequest.id))
        
        conditions = []
        if start:
            conditions.append(PurchaseRequest.created_at >= start)
        if end:
            conditions.append(PurchaseRequest.created_at < end)
        if requester_id:
            conditions.append(PurchaseRequest.requester_id == requester_id)
        
        if company_filter is not None:
            query = query.join(User, PurchaseRequest.requester_id == User.id)
            conditions.append(company_filter)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _count_active_campaigns(self) -> int:
        """활성 캠페인 개수"""
        query = select(func.count(Campaign.id)).where(
            Campaign.status == CampaignStatus.ACTIVE
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _count_pending_requests(self) -> int:
        """대기중인 구매요청 개수"""
        query = select(func.count(PurchaseRequest.id)).where(
            PurchaseRequest.status == RequestStatus.PENDING
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _count_company_users(self, company: str, active_only: bool = False) -> int:
        """회사 사용자 개수"""
        query = select(func.count(User.id)).where(User.company == company)
        
        if active_only:
            query = query.where(User.is_active == True)
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _count_user_pending_requests(self, user_id: int) -> int:
        """사용자의 대기중인 요청 개수"""
        query = select(func.count(PurchaseRequest.id)).where(
            and_(
                PurchaseRequest.requester_id == user_id,
                PurchaseRequest.status == RequestStatus.PENDING
            )
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _calculate_revenue_since(self, since: datetime) -> float:
        """특정 시간 이후 수익 계산"""
        campaign_query = select(func.sum(Campaign.budget)).where(
            and_(
                Campaign.created_at >= since,
                Campaign.status == CampaignStatus.COMPLETED
            )
        )
        
        result = await self.db.execute(campaign_query)
        return float(result.scalar() or 0.0)
    
    async def _calculate_company_revenue(self, company: str, since: datetime) -> float:
        """회사별 수익 계산"""
        query = select(func.sum(Campaign.budget)).join(
            User, Campaign.creator_id == User.id
        ).where(
            and_(
                User.company == company,
                Campaign.created_at >= since,
                Campaign.status == CampaignStatus.COMPLETED
            )
        )
        
        result = await self.db.execute(query)
        return float(result.scalar() or 0.0)
    
    async def _calculate_user_spending(self, user_id: int, since: datetime) -> float:
        """사용자 지출 계산"""
        # 캠페인 예산
        campaign_query = select(func.sum(Campaign.budget)).where(
            and_(
                Campaign.creator_id == user_id,
                Campaign.created_at >= since
            )
        )
        
        # 승인된 구매요청
        request_query = select(func.sum(PurchaseRequest.amount)).where(
            and_(
                PurchaseRequest.requester_id == user_id,
                PurchaseRequest.created_at >= since,
                PurchaseRequest.status.in_([RequestStatus.APPROVED, RequestStatus.COMPLETED])
            )
        )
        
        campaign_result = await self.db.execute(campaign_query)
        request_result = await self.db.execute(request_query)
        
        campaign_total = float(campaign_result.scalar() or 0.0)
        request_total = float(request_result.scalar() or 0.0)
        
        return campaign_total + request_total
    
    async def _get_system_performance_metrics(self) -> Dict[str, Any]:
        """시스템 성능 메트릭"""
        
        # 데이터베이스 연결 테스트
        db_start = time.time()
        await self.db.execute(text("SELECT 1"))
        db_latency = (time.time() - db_start) * 1000
        
        # 캐시 통계
        cache_stats = app_cache.get_stats()
        
        return {
            "database": {
                "latency_ms": round(db_latency, 2),
                "status": "healthy" if db_latency < 100 else "slow"
            },
            "cache": {
                "hit_ratio": round(
                    (cache_stats["active_items"] / max(cache_stats["total_items"], 1)) * 100, 2
                ),
                "active_items": cache_stats["active_items"],
                "total_items": cache_stats["total_items"]
            }
        }
    
    def _calculate_growth_rate(self, current: int, previous: int) -> float:
        """성장률 계산"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        
        growth = ((current - previous) / previous) * 100
        return round(growth, 2)