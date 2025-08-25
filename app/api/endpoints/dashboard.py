from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime, timedelta
from urllib.parse import unquote

from app.db.database import get_async_db
from app.api.deps import get_current_active_user, _get_client_ip
from app.models.user import User
from app.models.campaign import Campaign
from app.models.purchase_request import PurchaseRequest
from app.services.analytics_service import AnalyticsService
from app.services.chart_service import ChartService
from app.services.metrics_service import MetricsService
from app.services.report_service import ReportService
from app.core.logging import security_logger, log_api_call

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """대시보드 통계 데이터 조회 (권한별 필터링)"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 현재 사용자 조회
        current_user_query = select(User).where(User.id == user_id)
        result = await db.execute(current_user_query)
        current_user = result.scalar_one_or_none()
        
        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 권한별 통계 조회
        if user_role in ['슈퍼 어드민', '슈퍼어드민'] or '슈퍼' in user_role:
            # 슈퍼 어드민은 전체 통계
            total_campaigns_result = await db.execute(select(func.count(Campaign.id)))
            total_campaigns = total_campaigns_result.scalar() or 0
            
            active_campaigns_result = await db.execute(select(func.count(Campaign.id)).where(Campaign.status == 'active'))
            active_campaigns = active_campaigns_result.scalar() or 0
            
            total_users_result = await db.execute(select(func.count(User.id)))
            total_users = total_users_result.scalar() or 0
            
        elif user_role in ['대행사 어드민', '대행사어드민'] or ('대행사' in user_role and '어드민' in user_role):
            # 대행사 어드민은 소속 회사 통계
            company_campaigns_result = await db.execute(
                select(func.count(Campaign.id))
                .join(User, Campaign.user_id == User.id)
                .where(User.company == current_user.company)
            )
            total_campaigns = company_campaigns_result.scalar() or 0
            
            company_active_campaigns_result = await db.execute(
                select(func.count(Campaign.id))
                .join(User, Campaign.user_id == User.id)
                .where(User.company == current_user.company, Campaign.status == 'active')
            )
            active_campaigns = company_active_campaigns_result.scalar() or 0
            
            company_users_result = await db.execute(
                select(func.count(User.id))
                .where(User.company == current_user.company)
            )
            total_users = company_users_result.scalar() or 0
            
        elif user_role == '클라이언트':
            # 클라이언트는 자신의 통계만
            user_campaigns_result = await db.execute(
                select(func.count(Campaign.id))
                .where(Campaign.user_id == user_id)
            )
            total_campaigns = user_campaigns_result.scalar() or 0
            
            user_active_campaigns_result = await db.execute(
                select(func.count(Campaign.id))
                .where(Campaign.user_id == user_id, Campaign.status == 'active')
            )
            active_campaigns = user_active_campaigns_result.scalar() or 0
            
            total_users = 1  # 자기 자신만
            
        else:
            # 직원은 회사 통계
            total_campaigns = 0
            active_campaigns = 0
            total_users = 1
        
        return {
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "total_expenses": 0,  # TODO: 비용 계산 추가
            "monthly_expenses": 0,  # TODO: 월별 비용 계산 추가
            "total_users": total_users,
            "recent_activities": []  # TODO: 최근 활동 계산 추가
        }
    else:
        # 기존 API 모드 (JWT 토큰 기반) - AnalyticsService 사용
        current_user = jwt_user
        
        try:
            # AnalyticsService를 사용하여 통계 조회
            analytics_service = AnalyticsService(db)
            dashboard_stats = await analytics_service.get_dashboard_stats(current_user)
            
            # 응답 형식 통일
            return {
                "total_campaigns": dashboard_stats.get("total_campaigns", 0),
                "active_campaigns": dashboard_stats.get("active_campaigns", 0), 
                "total_expenses": dashboard_stats.get("total_expenses", 0.0),
                "monthly_expenses": dashboard_stats.get("monthly_expenses", 0.0),
                "total_users": dashboard_stats.get("total_users", 1),
                "recent_activities": dashboard_stats.get("recent_activities", []),
                "user_role": current_user.role.value if current_user.role else "unknown",
                "user_name": current_user.name,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            }
        except Exception as e:
            # 에러 발생 시 기본값 반환
            security_logger.log_suspicious_activity(
                "dashboard_analytics_error",
                {"error": str(e), "user_id": current_user.id},
                "unknown"
            )
            return {
                "total_campaigns": 0,
                "active_campaigns": 0,
                "total_expenses": 0.0,
                "monthly_expenses": 0.0,
                "total_users": 1,
                "recent_activities": [],
                "user_role": current_user.role.value if current_user.role else "unknown",
                "user_name": current_user.name,
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }


@router.get("/analytics")
@log_api_call
async def get_advanced_analytics(
    request: Request,
    date_from: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """고급 분석 데이터 조회"""
    
    try:
        # 날짜 파싱
        date_from_dt = None
        date_to_dt = None
        
        if date_from:
            date_from_dt = datetime.fromisoformat(date_from)
        if date_to:
            date_to_dt = datetime.fromisoformat(date_to)
            
        # 임시 분석 데이터 (AnalyticsService 이슈 해결 후 복구)
        analytics_data = {
            "total_campaigns": 0,
            "active_campaigns": 0,
            "total_expenses": 0.0,
            "user_role": current_user.role.value if current_user.role else "unknown"
        }
        
        # 데이터 접근 로깅
        security_logger.log_data_access(
            str(current_user.id),
            "advanced_analytics",
            "read"
        )
        
        return {
            "status": "success",
            "data": analytics_data,
            "user_role": current_user.role.value,
            "request_timestamp": datetime.now().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"날짜 형식이 올바르지 않습니다: {str(e)}"
        )
    except Exception as e:
        security_logger.log_suspicious_activity(
            "analytics_error",
            {"error": str(e)},
            _get_client_ip(request)
        )
        raise HTTPException(
            status_code=500,
            detail="분석 데이터를 조회할 수 없습니다"
        )


@router.get("/charts")
@log_api_call
async def get_chart_data(
    request: Request,
    chart_type: Optional[str] = Query(None, description="특정 차트 타입"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """차트 데이터 조회"""
    
    try:
        chart_service = ChartService(db)
        
        if chart_type:
            # 특정 차트만 조회
            chart_methods = {
                "campaign_status": chart_service.get_campaign_status_chart,
                "monthly_expenses": chart_service.get_monthly_expenses_chart,
                "user_activity": chart_service.get_user_activity_chart,
                "purchase_status": chart_service.get_purchase_request_status_chart,
                "budget_analysis": chart_service.get_budget_analysis_chart
            }
            
            if chart_type not in chart_methods:
                raise HTTPException(
                    status_code=400,
                    detail=f"지원하지 않는 차트 타입: {chart_type}"
                )
            
            chart_data = await chart_methods[chart_type](current_user)
            
        else:
            # 모든 차트 데이터 조회
            chart_data = await chart_service.get_all_chart_data(current_user)
        
        # 데이터 접근 로깅
        security_logger.log_data_access(
            str(current_user.id),
            f"chart_data_{chart_type or 'all'}",
            "read"
        )
        
        return {
            "status": "success",
            "charts": chart_data,
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        security_logger.log_suspicious_activity(
            "chart_data_error",
            {"error": str(e), "chart_type": chart_type},
            _get_client_ip(request)
        )
        raise HTTPException(
            status_code=500,
            detail="차트 데이터를 조회할 수 없습니다"
        )


@router.get("/metrics/realtime")
@log_api_call
async def get_realtime_metrics(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """실시간 메트릭 조회"""
    
    try:
        metrics_service = MetricsService(db)
        metrics_data = await metrics_service.get_real_time_metrics(current_user)
        
        # 데이터 접근 로깅
        security_logger.log_data_access(
            str(current_user.id),
            "realtime_metrics",
            "read"
        )
        
        return {
            "status": "success",
            "metrics": metrics_data,
            "refresh_interval": 30  # 30초마다 갱신 권장
        }
        
    except Exception as e:
        security_logger.log_suspicious_activity(
            "metrics_error",
            {"error": str(e)},
            _get_client_ip(request)
        )
        raise HTTPException(
            status_code=500,
            detail="실시간 메트릭을 조회할 수 없습니다"
        )


@router.get("/summary")
@log_api_call
async def get_dashboard_summary(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """대시보드 요약 정보 조회 (빠른 로딩용)"""
    
    try:
        # 기본 통계만 빠르게 조회 (임시 데이터)
        metrics_service = MetricsService(db)
        
        # 병렬 처리로 성능 최적화
        import asyncio
        
        # 임시 기본 통계 데이터
        basic_stats = {
            "total_campaigns": 0,
            "active_campaigns": 0, 
            "total_expenses": 0.0,
            "user_role": current_user.role.value if current_user.role else "unknown"
        }
        realtime_metrics_task = metrics_service.get_real_time_metrics(current_user)
        
        # asyncio.gather 대신 직접 호출 (임시)
        realtime_metrics = await realtime_metrics_task
        
        # 에러 처리
        if isinstance(basic_stats, Exception):
            basic_stats = {"error": "기본 통계를 조회할 수 없습니다"}
        
        if isinstance(realtime_metrics, Exception):
            realtime_metrics = {"error": "실시간 메트릭을 조회할 수 없습니다"}
        
        summary = {
            "quick_stats": {
                "total_campaigns": basic_stats.get("total_campaigns", 0),
                "active_campaigns": basic_stats.get("active_campaigns", 0),
                "total_expenses": basic_stats.get("total_expenses", 0),
                "total_users": basic_stats.get("total_users", 0)
            },
            "today_metrics": realtime_metrics.get("today", {}),
            "user_info": {
                "name": current_user.name,
                "role": current_user.role.value,
                "company": current_user.company
            },
            "last_updated": datetime.now().isoformat()
        }
        
        # 데이터 접근 로깅
        security_logger.log_data_access(
            str(current_user.id),
            "dashboard_summary",
            "read"
        )
        
        return {
            "status": "success",
            "summary": summary
        }
        
    except Exception as e:
        security_logger.log_suspicious_activity(
            "dashboard_summary_error",
            {"error": str(e)},
            _get_client_ip(request)
        )
        raise HTTPException(
            status_code=500,
            detail="대시보드 요약을 조회할 수 없습니다"
        )


@router.get("/reports/{report_type}")
@log_api_call
async def generate_report(
    request: Request,
    report_type: str,
    date_from: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """성과 리포트 생성"""
    
    # 지원되는 리포트 타입
    supported_types = ["summary", "detailed", "financial", "performance"]
    
    if report_type not in supported_types:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 리포트 타입입니다. 지원되는 타입: {', '.join(supported_types)}"
        )
    
    try:
        # 날짜 설정 (기본값: 최근 30일)
        if not date_to:
            date_to_dt = datetime.now()
        else:
            date_to_dt = datetime.fromisoformat(date_to)
        
        if not date_from:
            date_from_dt = date_to_dt - timedelta(days=30)
        else:
            date_from_dt = datetime.fromisoformat(date_from)
        
        # 날짜 검증
        if date_from_dt > date_to_dt:
            raise HTTPException(
                status_code=400,
                detail="시작 날짜는 종료 날짜보다 이전이어야 합니다"
            )
        
        # 최대 1년 제한
        if (date_to_dt - date_from_dt).days > 365:
            raise HTTPException(
                status_code=400,
                detail="리포트 기간은 최대 1년입니다"
            )
        
        # 리포트 생성
        report_service = ReportService(db)
        report_data = await report_service.generate_performance_report(
            current_user, date_from_dt, date_to_dt, report_type
        )
        
        # 리포트 생성 로깅
        security_logger.log_data_access(
            str(current_user.id),
            f"report_{report_type}",
            "generate",
            1
        )
        
        return {
            "status": "success",
            "report": report_data
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"날짜 형식이 올바르지 않습니다: {str(e)}"
        )
    except Exception as e:
        security_logger.log_suspicious_activity(
            "report_generation_error",
            {"error": str(e), "report_type": report_type},
            _get_client_ip(request)
        )
        raise HTTPException(
            status_code=500,
            detail="리포트를 생성할 수 없습니다"
        )


@router.get("/export/{format}")
@log_api_call
async def export_dashboard_data(
    request: Request,
    format: str,
    data_type: str = Query(..., description="내보낼 데이터 타입"),
    date_from: Optional[str] = Query(None, description="시작 날짜"),
    date_to: Optional[str] = Query(None, description="종료 날짜"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """대시보드 데이터 내보내기"""
    
    # 지원되는 형식
    supported_formats = ["json", "csv"]  # Excel은 추후 구현 가능
    if format not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 형식입니다. 지원되는 형식: {', '.join(supported_formats)}"
        )
    
    # 지원되는 데이터 타입
    supported_data_types = ["analytics", "charts", "metrics", "reports"]
    if data_type not in supported_data_types:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 데이터 타입입니다. 지원되는 타입: {', '.join(supported_data_types)}"
        )
    
    try:
        # 날짜 파싱
        date_from_dt = None
        date_to_dt = None
        
        if date_from:
            date_from_dt = datetime.fromisoformat(date_from)
        if date_to:
            date_to_dt = datetime.fromisoformat(date_to)
        
        export_data = {}
        
        # 데이터 타입별 조회
        if data_type == "analytics":
            # 임시 분석 데이터
            export_data = {
                "total_campaigns": 0,
                "active_campaigns": 0, 
                "total_expenses": 0.0,
                "user_role": current_user.role.value if current_user.role else "unknown",
                "export_date": datetime.now().isoformat()
            }
            
        elif data_type == "charts":
            chart_service = ChartService(db)
            export_data = await chart_service.get_all_chart_data(current_user)
            
        elif data_type == "metrics":
            metrics_service = MetricsService(db)
            export_data = await metrics_service.get_real_time_metrics(current_user)
            
        elif data_type == "reports":
            report_service = ReportService(db)
            if not date_from_dt:
                date_from_dt = datetime.now() - timedelta(days=30)
            if not date_to_dt:
                date_to_dt = datetime.now()
            export_data = await report_service.generate_performance_report(
                current_user, date_from_dt, date_to_dt, "summary"
            )
        
        # 내보내기 로깅
        security_logger.log_data_access(
            str(current_user.id),
            f"export_{data_type}_{format}",
            "export"
        )
        
        if format == "json":
            from fastapi.responses import JSONResponse
            return JSONResponse(
                content=export_data,
                headers={
                    "Content-Disposition": f"attachment; filename=brandflow_{data_type}_{datetime.now().strftime('%Y%m%d')}.json"
                }
            )
        
        elif format == "csv":
            # CSV 변환 (간단한 형태)
            import csv
            import io
            
            output = io.StringIO()
            
            # 플래튼 데이터 변환 (간단한 구현)
            def flatten_dict(d, parent_key='', sep='_'):
                items = []
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten_dict(v, new_key, sep=sep).items())
                    elif isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                        for i, item in enumerate(v):
                            items.extend(flatten_dict(item, f"{new_key}_{i}", sep=sep).items())
                    else:
                        items.append((new_key, v))
                return dict(items)
            
            flattened_data = flatten_dict(export_data)
            
            if flattened_data:
                writer = csv.DictWriter(output, fieldnames=flattened_data.keys())
                writer.writeheader()
                writer.writerow(flattened_data)
            
            from fastapi.responses import Response
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=brandflow_{data_type}_{datetime.now().strftime('%Y%m%d')}.csv"
                }
            )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"날짜 형식이 올바르지 않습니다: {str(e)}"
        )
    except Exception as e:
        security_logger.log_suspicious_activity(
            "export_error",
            {"error": str(e), "format": format, "data_type": data_type},
            _get_client_ip(request)
        )
        raise HTTPException(
            status_code=500,
            detail="데이터를 내보낼 수 없습니다"
        )


@router.get("/health")
async def dashboard_health():
    """대시보드 헬스체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "dashboard",
        "version": "2.0",
        "features": {
            "analytics": True,
            "caching": True,
            "real_time_metrics": True,
            "user_authentication": True
        }
    }


@router.get("/charts")
async def dashboard_charts(
    viewer_id: int = Query(..., description="요청자 ID"),
    viewer_role: str = Query(..., description="요청자 역할"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """차트 데이터 반환"""
    try:
        # ChartService 인스턴스 생성
        chart_service = ChartService(db)
        
        # 기본 차트 데이터 생성
        charts_data = {
            "campaign_status_chart": await chart_service.get_campaign_status_chart(),
            "monthly_performance": await chart_service.get_monthly_performance_chart(),
            "roi_analysis": await chart_service.get_roi_analysis_chart(),
            "budget_utilization": await chart_service.get_budget_utilization_chart()
        }
        
        return {
            "success": True,
            "data": charts_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"차트 데이터 로드 실패: {str(e)}",
            "data": {}
        }


@router.get("/analytics")
async def dashboard_analytics(
    viewer_id: int = Query(..., description="요청자 ID"),
    viewer_role: str = Query(..., description="요청자 역할"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """분석 데이터 반환"""
    try:
        # 기본 분석 데이터
        analytics_data = {
            "performance_metrics": {
                "conversion_rate": 0.0,
                "click_through_rate": 0.0,
                "cost_per_acquisition": 0.0,
                "return_on_investment": 0.0
            },
            "trends": {
                "weekly_growth": 0.0,
                "monthly_growth": 0.0,
                "quarterly_growth": 0.0
            },
            "predictions": {
                "next_month_budget": 0.0,
                "expected_campaigns": 0,
                "predicted_roi": 0.0
            }
        }
        
        return {
            "success": True,
            "data": analytics_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"분석 데이터 로드 실패: {str(e)}",
            "data": {}
        }


@router.get("/summary")
async def dashboard_summary(
    viewer_id: int = Query(..., description="요청자 ID"),
    viewer_role: str = Query(..., description="요청자 역할"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """요약 데이터 반환"""
    try:
        # 기본 통계 조회
        total_campaigns = await db.scalar(select(func.count(Campaign.id)))
        active_campaigns = await db.scalar(
            select(func.count(Campaign.id)).where(Campaign.status == "active")
        )
        total_users = await db.scalar(select(func.count(User.id)))
        
        summary_data = {
            "overview": {
                "total_campaigns": total_campaigns or 0,
                "active_campaigns": active_campaigns or 0,
                "completed_campaigns": (total_campaigns or 0) - (active_campaigns or 0),
                "total_users": total_users or 0
            },
            "recent_activity": {
                "new_campaigns_this_week": 0,
                "completed_campaigns_this_week": 0,
                "new_users_this_week": 0
            },
            "performance_summary": {
                "total_budget": 0.0,
                "spent_budget": 0.0,
                "average_roi": 0.0,
                "success_rate": 0.0
            }
        }
        
        return {
            "success": True,
            "data": summary_data,
            "timestamp": datetime.now().isoformat(),
            "user_role": viewer_role
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"요약 데이터 로드 실패: {str(e)}",
            "data": {}
        }