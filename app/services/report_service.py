"""
Report and performance analysis service for BrandFlow API
성과 분석 및 리포트 생성 서비스
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, case, extract
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json

from app.models.user import User, UserRole
from app.models.campaign import Campaign, CampaignStatus
from app.models.purchase_request import PurchaseRequest, RequestStatus
from app.core.cache import cached


class ReportService:
    """성과 분석 및 리포트 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    @cached(ttl=1800, key_prefix="performance_report_")
    async def generate_performance_report(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime,
        report_type: str = "summary"
    ) -> Dict[str, Any]:
        """성과 리포트 생성"""
        
        report = {
            "report_info": {
                "type": report_type,
                "generated_by": user.name,
                "user_role": user.role.value,
                "company": user.company,
                "period": {
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                    "days": (date_to - date_from).days + 1
                },
                "generated_at": datetime.now().isoformat()
            }
        }
        
        if report_type == "summary":
            report.update(await self._generate_summary_report(user, date_from, date_to))
        elif report_type == "detailed":
            report.update(await self._generate_detailed_report(user, date_from, date_to))
        elif report_type == "financial":
            report.update(await self._generate_financial_report(user, date_from, date_to))
        elif report_type == "performance":
            report.update(await self._generate_performance_analysis(user, date_from, date_to))
        else:
            report.update(await self._generate_summary_report(user, date_from, date_to))
        
        return report
    
    async def _generate_summary_report(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """요약 리포트 생성"""
        
        # 기본 통계
        campaign_stats = await self._get_campaign_statistics(user, date_from, date_to)
        financial_stats = await self._get_financial_statistics(user, date_from, date_to)
        efficiency_stats = await self._get_efficiency_metrics(user, date_from, date_to)
        
        # 주요 성과 지표 (KPI)
        kpis = await self._calculate_key_performance_indicators(user, date_from, date_to)
        
        # 트렌드 분석
        trends = await self._analyze_trends(user, date_from, date_to)
        
        return {
            "summary": {
                "campaign_overview": campaign_stats,
                "financial_overview": financial_stats,
                "efficiency_metrics": efficiency_stats,
                "key_performance_indicators": kpis,
                "trend_analysis": trends
            }
        }
    
    async def _generate_detailed_report(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """상세 리포트 생성"""
        
        # 캠페인별 상세 분석
        campaign_details = await self._get_detailed_campaign_analysis(user, date_from, date_to)
        
        # 사용자별 성과 (권한이 있는 경우)
        user_performance = await self._get_user_performance_analysis(user, date_from, date_to)
        
        # 시간대별 분석
        time_analysis = await self._get_time_based_analysis(user, date_from, date_to)
        
        return {
            "detailed_analysis": {
                "campaign_breakdown": campaign_details,
                "user_performance": user_performance,
                "temporal_analysis": time_analysis,
                "recommendations": await self._generate_recommendations(user, date_from, date_to)
            }
        }
    
    async def _generate_financial_report(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """재무 리포트 생성"""
        
        # 수입/지출 분석
        revenue_analysis = await self._analyze_revenue_streams(user, date_from, date_to)
        expense_analysis = await self._analyze_expense_patterns(user, date_from, date_to)
        
        # 예산 대비 실적
        budget_analysis = await self._analyze_budget_performance(user, date_from, date_to)
        
        # ROI 계산
        roi_analysis = await self._calculate_return_on_investment(user, date_from, date_to)
        
        # 비용 효율성
        cost_efficiency = await self._analyze_cost_efficiency(user, date_from, date_to)
        
        return {
            "financial_analysis": {
                "revenue_breakdown": revenue_analysis,
                "expense_breakdown": expense_analysis,
                "budget_performance": budget_analysis,
                "roi_analysis": roi_analysis,
                "cost_efficiency": cost_efficiency
            }
        }
    
    async def _generate_performance_analysis(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """성과 분석 리포트 생성"""
        
        # 목표 대비 성과
        goal_performance = await self._analyze_goal_achievement(user, date_from, date_to)
        
        # 경쟁력 분석 (권한이 있는 경우)
        competitive_analysis = await self._analyze_competitive_position(user, date_from, date_to)
        
        # 성장률 분석
        growth_analysis = await self._analyze_growth_rates(user, date_from, date_to)
        
        # 품질 지표
        quality_metrics = await self._analyze_quality_metrics(user, date_from, date_to)
        
        return {
            "performance_analysis": {
                "goal_achievement": goal_performance,
                "competitive_position": competitive_analysis,
                "growth_metrics": growth_analysis,
                "quality_indicators": quality_metrics,
                "improvement_areas": await self._identify_improvement_areas(user, date_from, date_to)
            }
        }
    
    # 헬퍼 메서드들
    async def _get_campaign_statistics(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """캠페인 통계 조회"""
        
        base_query = select(Campaign).where(
            and_(
                Campaign.created_at >= date_from,
                Campaign.created_at <= date_to
            )
        )
        
        # 권한별 필터링
        if user.role == UserRole.AGENCY_ADMIN:
            base_query = base_query.join(User, Campaign.creator_id == User.id).where(
                User.company == user.company
            )
        elif user.role == UserRole.CLIENT:
            base_query = base_query.where(Campaign.creator_id == user.id)
        elif user.role == UserRole.STAFF:
            return {"error": "권한이 부족합니다"}
        
        # 상태별 통계
        status_stats = await self.db.execute(
            select(
                Campaign.status,
                func.count(Campaign.id).label('count'),
                func.sum(Campaign.budget).label('total_budget'),
                func.avg(Campaign.budget).label('avg_budget')
            ).where(
                and_(
                    Campaign.created_at >= date_from,
                    Campaign.created_at <= date_to
                )
            ).group_by(Campaign.status)
        )
        
        stats_by_status = {}
        total_campaigns = 0
        total_budget = 0.0
        
        for row in status_stats:
            status = row.status.value if row.status else "unknown"
            stats_by_status[status] = {
                "count": row.count,
                "total_budget": float(row.total_budget or 0),
                "avg_budget": float(row.avg_budget or 0)
            }
            total_campaigns += row.count
            total_budget += float(row.total_budget or 0)
        
        return {
            "total_campaigns": total_campaigns,
            "total_budget": total_budget,
            "avg_budget_per_campaign": total_budget / max(total_campaigns, 1),
            "status_breakdown": stats_by_status,
            "completion_rate": (
                stats_by_status.get("완료", {}).get("count", 0) / max(total_campaigns, 1) * 100
            )
        }
    
    async def _get_financial_statistics(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """재무 통계 조회"""
        
        # 캠페인 예산 통계
        campaign_budget_query = select(
            func.sum(Campaign.budget).label('total_budget'),
            func.avg(Campaign.budget).label('avg_budget'),
            func.count(Campaign.id).label('campaign_count')
        ).where(
            and_(
                Campaign.created_at >= date_from,
                Campaign.created_at <= date_to
            )
        )
        
        # 구매요청 통계
        purchase_amount_query = select(
            func.sum(PurchaseRequest.amount).label('total_requests'),
            func.avg(PurchaseRequest.amount).label('avg_request'),
            func.count(PurchaseRequest.id).label('request_count')
        ).where(
            and_(
                PurchaseRequest.created_at >= date_from,
                PurchaseRequest.created_at <= date_to,
                PurchaseRequest.status.in_([RequestStatus.APPROVED, RequestStatus.COMPLETED])
            )
        )
        
        # 권한별 필터링
        if user.role == UserRole.AGENCY_ADMIN:
            campaign_budget_query = campaign_budget_query.join(
                User, Campaign.creator_id == User.id
            ).where(User.company == user.company)
            
            purchase_amount_query = purchase_amount_query.join(
                User, PurchaseRequest.requester_id == User.id
            ).where(User.company == user.company)
            
        elif user.role == UserRole.CLIENT:
            campaign_budget_query = campaign_budget_query.where(Campaign.creator_id == user.id)
            purchase_amount_query = purchase_amount_query.where(PurchaseRequest.requester_id == user.id)
        
        # 실행
        campaign_result = await self.db.execute(campaign_budget_query)
        purchase_result = await self.db.execute(purchase_amount_query)
        
        campaign_row = campaign_result.first()
        purchase_row = purchase_result.first()
        
        total_budget = float(campaign_row.total_budget or 0)
        total_spent = float(purchase_row.total_requests or 0)
        
        return {
            "total_budget_allocated": total_budget,
            "total_amount_spent": total_spent,
            "budget_utilization_rate": (total_spent / max(total_budget, 1)) * 100,
            "remaining_budget": max(total_budget - total_spent, 0),
            "average_campaign_budget": float(campaign_row.avg_budget or 0),
            "average_purchase_amount": float(purchase_row.avg_request or 0),
            "campaign_count": campaign_row.campaign_count or 0,
            "approved_requests_count": purchase_row.request_count or 0
        }
    
    async def _get_efficiency_metrics(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """효율성 지표 계산"""
        
        # 캠페인 완료 시간 분석
        completion_time_query = select(
            func.avg(
                func.julianday(Campaign.updated_at) - func.julianday(Campaign.created_at)
            ).label('avg_completion_days')
        ).where(
            and_(
                Campaign.created_at >= date_from,
                Campaign.created_at <= date_to,
                Campaign.status == CampaignStatus.COMPLETED
            )
        )
        
        # 구매요청 승인 시간
        approval_time_query = select(
            func.avg(
                func.julianday(PurchaseRequest.updated_at) - func.julianday(PurchaseRequest.created_at)
            ).label('avg_approval_days')
        ).where(
            and_(
                PurchaseRequest.created_at >= date_from,
                PurchaseRequest.created_at <= date_to,
                PurchaseRequest.status == RequestStatus.APPROVED
            )
        )
        
        completion_result = await self.db.execute(completion_time_query)
        approval_result = await self.db.execute(approval_time_query)
        
        avg_completion = completion_result.scalar() or 0
        avg_approval = approval_result.scalar() or 0
        
        return {
            "average_campaign_completion_days": round(avg_completion, 2),
            "average_request_approval_days": round(avg_approval, 2),
            "efficiency_score": max(100 - (avg_completion * 2) - (avg_approval * 5), 0),
            "process_optimization_potential": {
                "campaign_completion": "high" if avg_completion > 30 else "medium" if avg_completion > 14 else "low",
                "request_approval": "high" if avg_approval > 7 else "medium" if avg_approval > 3 else "low"
            }
        }
    
    async def _calculate_key_performance_indicators(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """주요 성과 지표 (KPI) 계산"""
        
        # 이전 기간과 비교를 위한 날짜 계산
        period_days = (date_to - date_from).days + 1
        prev_date_to = date_from - timedelta(days=1)
        prev_date_from = prev_date_to - timedelta(days=period_days - 1)
        
        # 현재 기간 데이터
        current_stats = await self._get_campaign_statistics(user, date_from, date_to)
        current_financial = await self._get_financial_statistics(user, date_from, date_to)
        
        # 이전 기간 데이터
        prev_stats = await self._get_campaign_statistics(user, prev_date_from, prev_date_to)
        prev_financial = await self._get_financial_statistics(user, prev_date_from, prev_date_to)
        
        # 성장률 계산
        def calculate_growth(current: float, previous: float) -> float:
            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return ((current - previous) / previous) * 100
        
        kpis = {
            "campaign_growth": {
                "value": calculate_growth(
                    current_stats["total_campaigns"], 
                    prev_stats["total_campaigns"]
                ),
                "unit": "%",
                "trend": "up" if current_stats["total_campaigns"] > prev_stats["total_campaigns"] else "down"
            },
            "budget_growth": {
                "value": calculate_growth(
                    current_financial["total_budget_allocated"],
                    prev_financial["total_budget_allocated"]
                ),
                "unit": "%",
                "trend": "up" if current_financial["total_budget_allocated"] > prev_financial["total_budget_allocated"] else "down"
            },
            "completion_rate": {
                "value": current_stats["completion_rate"],
                "unit": "%",
                "trend": "up" if current_stats["completion_rate"] > 70 else "down",
                "target": 80.0
            },
            "budget_utilization": {
                "value": current_financial["budget_utilization_rate"],
                "unit": "%",
                "trend": "up" if current_financial["budget_utilization_rate"] > 75 else "down",
                "target": 85.0
            }
        }
        
        return kpis
    
    async def _analyze_trends(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> Dict[str, Any]:
        """트렌드 분석"""
        
        # 주간별 캠페인 생성 트렌드
        weekly_trends = await self.db.execute(
            select(
                func.strftime('%Y-%W', Campaign.created_at).label('week'),
                func.count(Campaign.id).label('campaign_count'),
                func.sum(Campaign.budget).label('weekly_budget')
            ).where(
                and_(
                    Campaign.created_at >= date_from,
                    Campaign.created_at <= date_to
                )
            ).group_by(
                func.strftime('%Y-%W', Campaign.created_at)
            ).order_by('week')
        )
        
        trend_data = []
        for row in weekly_trends:
            trend_data.append({
                "period": row.week,
                "campaigns": row.campaign_count,
                "budget": float(row.weekly_budget or 0)
            })
        
        # 전반적인 트렌드 방향 계산
        if len(trend_data) >= 2:
            first_half = trend_data[:len(trend_data)//2]
            second_half = trend_data[len(trend_data)//2:]
            
            first_avg = sum(item["campaigns"] for item in first_half) / len(first_half)
            second_avg = sum(item["campaigns"] for item in second_half) / len(second_half)
            
            trend_direction = "increasing" if second_avg > first_avg else "decreasing"
        else:
            trend_direction = "stable"
        
        return {
            "weekly_data": trend_data,
            "overall_trend": trend_direction,
            "trend_strength": abs((second_avg - first_avg) / max(first_avg, 1)) * 100 if len(trend_data) >= 2 else 0
        }
    
    async def _generate_recommendations(
        self, 
        user: User, 
        date_from: datetime, 
        date_to: datetime
    ) -> List[Dict[str, Any]]:
        """개선 권장사항 생성"""
        
        recommendations = []
        
        # 성과 데이터 조회
        campaign_stats = await self._get_campaign_statistics(user, date_from, date_to)
        financial_stats = await self._get_financial_statistics(user, date_from, date_to)
        
        # 완료율이 낮은 경우
        if campaign_stats["completion_rate"] < 60:
            recommendations.append({
                "category": "process_improvement",
                "priority": "high",
                "title": "캠페인 완료율 개선",
                "description": f"현재 완료율 {campaign_stats['completion_rate']:.1f}%로 목표치(80%)에 미달합니다.",
                "suggested_actions": [
                    "캠페인 진행 과정 모니터링 강화",
                    "중간 점검 프로세스 도입",
                    "리소스 할당 최적화"
                ]
            })
        
        # 예산 활용도가 낮은 경우
        if financial_stats["budget_utilization_rate"] < 60:
            recommendations.append({
                "category": "budget_optimization",
                "priority": "medium",
                "title": "예산 활용도 증대",
                "description": f"현재 예산 활용도 {financial_stats['budget_utilization_rate']:.1f}%로 개선 여지가 있습니다.",
                "suggested_actions": [
                    "미사용 예산 재배분",
                    "추가 마케팅 활동 검토",
                    "예산 계획 정확도 향상"
                ]
            })
        
        # 캠페인 수가 적은 경우
        if campaign_stats["total_campaigns"] < 5:
            recommendations.append({
                "category": "activity_increase",
                "priority": "medium",
                "title": "캠페인 활동 증대",
                "description": "캠페인 수가 적어 사업 성장에 제약이 있을 수 있습니다.",
                "suggested_actions": [
                    "새로운 마케팅 채널 탐색",
                    "캠페인 기획 역량 강화",
                    "목표 고객층 확대"
                ]
            })
        
        return recommendations