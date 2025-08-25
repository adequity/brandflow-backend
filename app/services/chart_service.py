"""
Chart data service for BrandFlow API
데이터 시각화를 위한 차트 데이터 생성 서비스
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, extract, case, desc
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, date
import calendar

from app.models.user import User, UserRole
from app.models.campaign import Campaign, CampaignStatus
from app.models.purchase_request import PurchaseRequest, RequestStatus
from app.core.cache import cached


class ChartService:
    """차트 데이터 생성 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    @cached(ttl=600, key_prefix="chart_campaign_status_")
    async def get_campaign_status_chart(self, user: User) -> Dict[str, Any]:
        """캠페인 상태별 차트 데이터"""
        
        # 권한별 필터링
        query = select(
            Campaign.status,
            func.count(Campaign.id).label('count')
        )
        
        # 사용자 권한에 따른 필터링
        if user.role == UserRole.SUPER_ADMIN:
            # 전체 데이터
            pass
        elif user.role == UserRole.AGENCY_ADMIN:
            # 회사별 필터링
            query = query.join(User, Campaign.creator_id == User.id).where(
                User.company == user.company
            )
        elif user.role == UserRole.CLIENT:
            # 개인 데이터만
            query = query.where(Campaign.creator_id == user.id)
        else:
            # 직원은 빈 데이터
            return {"labels": [], "data": [], "total": 0}
        
        query = query.group_by(Campaign.status)
        result = await self.db.execute(query)
        
        # 차트 데이터 구성
        labels = []
        data = []
        colors = {
            CampaignStatus.DRAFT: "#FFA500",      # Orange
            CampaignStatus.ACTIVE: "#4CAF50",     # Green
            CampaignStatus.COMPLETED: "#2196F3",  # Blue
            CampaignStatus.CANCELLED: "#F44336"   # Red
        }
        
        chart_colors = []
        total = 0
        
        for row in result:
            if row.status:
                labels.append(row.status.value)
                data.append(row.count)
                chart_colors.append(colors.get(row.status, "#9E9E9E"))
                total += row.count
        
        return {
            "type": "doughnut",
            "labels": labels,
            "data": data,
            "backgroundColor": chart_colors,
            "total": total,
            "title": "캠페인 상태 분포"
        }
    
    @cached(ttl=900, key_prefix="chart_monthly_expenses_")
    async def get_monthly_expenses_chart(
        self, 
        user: User, 
        months: int = 12
    ) -> Dict[str, Any]:
        """월별 비용 트렌드 차트 데이터"""
        
        # 기간 설정
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30 * months)
        
        # 기본 쿼리 - 캠페인 예산
        campaign_query = select(
            extract('year', Campaign.created_at).label('year'),
            extract('month', Campaign.created_at).label('month'),
            func.sum(Campaign.budget).label('campaign_total')
        ).where(
            and_(
                Campaign.created_at >= start_date,
                Campaign.created_at <= end_date
            )
        )
        
        # 구매요청 쿼리
        request_query = select(
            extract('year', PurchaseRequest.created_at).label('year'),
            extract('month', PurchaseRequest.created_at).label('month'),
            func.sum(PurchaseRequest.amount).label('request_total')
        ).where(
            and_(
                PurchaseRequest.created_at >= start_date,
                PurchaseRequest.created_at <= end_date,
                PurchaseRequest.status == RequestStatus.APPROVED
            )
        )
        
        # 권한별 필터링
        if user.role == UserRole.AGENCY_ADMIN:
            campaign_query = campaign_query.join(
                User, Campaign.creator_id == User.id
            ).where(User.company == user.company)
            
            request_query = request_query.join(
                User, PurchaseRequest.requester_id == User.id
            ).where(User.company == user.company)
            
        elif user.role == UserRole.CLIENT:
            campaign_query = campaign_query.where(Campaign.creator_id == user.id)
            request_query = request_query.where(PurchaseRequest.requester_id == user.id)
        
        elif user.role == UserRole.STAFF:
            return {"labels": [], "datasets": [], "title": "월별 비용 트렌드"}
        
        # 그룹화 및 정렬
        campaign_query = campaign_query.group_by(
            extract('year', Campaign.created_at),
            extract('month', Campaign.created_at)
        ).order_by(
            extract('year', Campaign.created_at),
            extract('month', Campaign.created_at)
        )
        
        request_query = request_query.group_by(
            extract('year', PurchaseRequest.created_at),
            extract('month', PurchaseRequest.created_at)
        ).order_by(
            extract('year', PurchaseRequest.created_at),
            extract('month', PurchaseRequest.created_at)
        )
        
        # 데이터 조회
        campaign_result = await self.db.execute(campaign_query)
        request_result = await self.db.execute(request_query)
        
        # 데이터 정리
        campaign_data = {}
        for row in campaign_result:
            key = f"{int(row.year)}-{int(row.month):02d}"
            campaign_data[key] = float(row.campaign_total or 0)
        
        request_data = {}
        for row in request_result:
            key = f"{int(row.year)}-{int(row.month):02d}"
            request_data[key] = float(row.request_total or 0)
        
        # 월별 라벨 생성
        labels = []
        campaign_amounts = []
        request_amounts = []
        
        current_date = start_date
        while current_date <= end_date:
            key = f"{current_date.year}-{current_date.month:02d}"
            month_name = calendar.month_abbr[current_date.month]
            labels.append(f"{month_name} {current_date.year}")
            
            campaign_amounts.append(campaign_data.get(key, 0))
            request_amounts.append(request_data.get(key, 0))
            
            # 다음 달로 이동 (날짜 오버플로우 방지)
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1, day=1)
        
        return {
            "type": "line",
            "labels": labels,
            "datasets": [
                {
                    "label": "캠페인 예산",
                    "data": campaign_amounts,
                    "borderColor": "#2196F3",
                    "backgroundColor": "rgba(33, 150, 243, 0.1)",
                    "fill": True
                },
                {
                    "label": "승인된 구매요청",
                    "data": request_amounts,
                    "borderColor": "#FF9800",
                    "backgroundColor": "rgba(255, 152, 0, 0.1)",
                    "fill": True
                }
            ],
            "title": "월별 비용 트렌드"
        }
    
    @cached(ttl=300, key_prefix="chart_user_activity_")
    async def get_user_activity_chart(self, user: User) -> Dict[str, Any]:
        """사용자 활동 차트 (권한이 있는 경우만)"""
        
        if user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
            return {"labels": [], "data": [], "title": "사용자 활동"}
        
        # 기간 설정 (최근 7일)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # 사용자별 활동 조회 쿼리
        campaign_activity = select(
            User.name,
            func.count(Campaign.id).label('campaign_count')
        ).join(
            Campaign, User.id == Campaign.creator_id
        ).where(
            Campaign.created_at >= start_date
        )
        
        # 권한별 필터링
        if user.role == UserRole.AGENCY_ADMIN:
            campaign_activity = campaign_activity.where(User.company == user.company)
        
        campaign_activity = campaign_activity.group_by(User.id, User.name).order_by(
            desc('campaign_count')
        ).limit(10)
        
        result = await self.db.execute(campaign_activity)
        
        labels = []
        data = []
        
        for row in result:
            labels.append(row.name)
            data.append(row.campaign_count)
        
        return {
            "type": "bar",
            "labels": labels,
            "data": data,
            "backgroundColor": "#4CAF50",
            "title": "최근 7일 사용자 활동 (캠페인 생성)"
        }
    
    @cached(ttl=600, key_prefix="chart_purchase_status_")
    async def get_purchase_request_status_chart(self, user: User) -> Dict[str, Any]:
        """구매요청 상태별 차트 데이터"""
        
        query = select(
            PurchaseRequest.status,
            func.count(PurchaseRequest.id).label('count')
        )
        
        # 권한별 필터링
        if user.role == UserRole.SUPER_ADMIN:
            pass
        elif user.role == UserRole.AGENCY_ADMIN:
            query = query.join(User, PurchaseRequest.requester_id == User.id).where(
                User.company == user.company
            )
        elif user.role == UserRole.CLIENT:
            query = query.where(PurchaseRequest.requester_id == user.id)
        else:
            return {"labels": [], "data": [], "total": 0}
        
        query = query.group_by(PurchaseRequest.status)
        result = await self.db.execute(query)
        
        labels = []
        data = []
        colors = {
            RequestStatus.PENDING: "#FFC107",     # Amber
            RequestStatus.APPROVED: "#4CAF50",    # Green
            RequestStatus.REJECTED: "#F44336",    # Red
            RequestStatus.COMPLETED: "#2196F3"    # Blue
        }
        
        chart_colors = []
        total = 0
        
        for row in result:
            if row.status:
                labels.append(row.status.value)
                data.append(row.count)
                chart_colors.append(colors.get(row.status, "#9E9E9E"))
                total += row.count
        
        return {
            "type": "pie",
            "labels": labels,
            "data": data,
            "backgroundColor": chart_colors,
            "total": total,
            "title": "구매요청 상태 분포"
        }
    
    @cached(ttl=900, key_prefix="chart_budget_analysis_")
    async def get_budget_analysis_chart(self, user: User) -> Dict[str, Any]:
        """예산 분석 차트 (예산 vs 실제 지출)"""
        
        # 캠페인별 예산과 실제 구매요청 금액 비교
        query = select(
            Campaign.name,
            Campaign.budget,
            func.coalesce(func.sum(PurchaseRequest.amount), 0).label('actual_spent')
        ).outerjoin(
            PurchaseRequest, and_(
                PurchaseRequest.campaign_id == Campaign.id,
                PurchaseRequest.status.in_([RequestStatus.APPROVED, RequestStatus.COMPLETED])
            )
        )
        
        # 권한별 필터링
        if user.role == UserRole.SUPER_ADMIN:
            pass
        elif user.role == UserRole.AGENCY_ADMIN:
            query = query.join(User, Campaign.creator_id == User.id).where(
                User.company == user.company
            )
        elif user.role == UserRole.CLIENT:
            query = query.where(Campaign.creator_id == user.id)
        else:
            return {"labels": [], "datasets": [], "title": "예산 vs 실제 지출"}
        
        query = query.group_by(Campaign.id, Campaign.name, Campaign.budget).order_by(
            desc(Campaign.budget)
        ).limit(10)
        
        result = await self.db.execute(query)
        
        labels = []
        budgets = []
        actual_spent = []
        
        for row in result:
            labels.append(row.name[:20] + "..." if len(row.name) > 20 else row.name)
            budgets.append(float(row.budget))
            actual_spent.append(float(row.actual_spent))
        
        return {
            "type": "bar",
            "labels": labels,
            "datasets": [
                {
                    "label": "예산",
                    "data": budgets,
                    "backgroundColor": "rgba(33, 150, 243, 0.8)",
                    "borderColor": "#2196F3",
                    "borderWidth": 1
                },
                {
                    "label": "실제 지출",
                    "data": actual_spent,
                    "backgroundColor": "rgba(255, 152, 0, 0.8)",
                    "borderColor": "#FF9800",
                    "borderWidth": 1
                }
            ],
            "title": "예산 vs 실제 지출 (상위 10개 캠페인)"
        }
    
    async def get_all_chart_data(self, user: User) -> Dict[str, Any]:
        """모든 차트 데이터를 한 번에 조회"""
        
        return {
            "campaign_status": await self.get_campaign_status_chart(user),
            "monthly_expenses": await self.get_monthly_expenses_chart(user),
            "user_activity": await self.get_user_activity_chart(user),
            "purchase_status": await self.get_purchase_request_status_chart(user),
            "budget_analysis": await self.get_budget_analysis_chart(user)
        }