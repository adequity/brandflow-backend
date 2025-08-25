"""
데이터 내보내기 엔드포인트
Excel, PDF, CSV 형식으로 데이터 내보내기 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Literal
from datetime import datetime, timedelta

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.campaign import Campaign
from app.models.purchase_request import PurchaseRequest
from app.services.export_service import export_service
from app.core.websocket import manager

router = APIRouter()

@router.post("/campaigns/excel")
async def export_campaigns_to_excel(
    background_tasks: BackgroundTasks,
    status_filter: Optional[str] = Query(None, description="상태 필터"),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    캠페인 데이터를 Excel로 내보내기
    
    - **status_filter**: 상태 필터 (선택사항)
    - **date_from**: 조회 시작일 (선택사항)
    - **date_to**: 조회 종료일 (선택사항)
    """
    try:
        # 캠페인 조회 쿼리 구성
        query = select(Campaign)
        
        if status_filter:
            query = query.where(Campaign.status == status_filter)
        
        if date_from:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.where(Campaign.created_at >= start_date)
        
        if date_to:
            end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.where(Campaign.created_at < end_date)
        
        result = await db.execute(query)
        campaigns = result.scalars().all()
        
        if not campaigns:
            raise HTTPException(status_code=404, detail="내보낼 캠페인 데이터가 없습니다.")
        
        # 백그라운드에서 Excel 파일 생성
        background_tasks.add_task(
            export_service.export_campaigns_excel,
            campaigns,
            current_user.id
        )
        
        return {
            "message": f"{len(campaigns)}개 캠페인 데이터의 Excel 내보내기를 시작했습니다.",
            "total_campaigns": len(campaigns),
            "status": "processing"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"잘못된 날짜 형식입니다: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel 내보내기 실패: {str(e)}")

@router.post("/campaigns/pdf")
async def export_campaigns_to_pdf(
    background_tasks: BackgroundTasks,
    status_filter: Optional[str] = Query(None, description="상태 필터"),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    캠페인 데이터를 PDF 리포트로 내보내기
    
    - **status_filter**: 상태 필터 (선택사항)
    - **date_from**: 조회 시작일 (선택사항)
    - **date_to**: 조회 종료일 (선택사항)
    """
    try:
        # 캠페인 조회 쿼리 구성
        query = select(Campaign)
        
        if status_filter:
            query = query.where(Campaign.status == status_filter)
        
        if date_from:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.where(Campaign.created_at >= start_date)
        
        if date_to:
            end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.where(Campaign.created_at < end_date)
        
        result = await db.execute(query)
        campaigns = result.scalars().all()
        
        if not campaigns:
            raise HTTPException(status_code=404, detail="내보낼 캠페인 데이터가 없습니다.")
        
        # 백그라운드에서 PDF 리포트 생성
        background_tasks.add_task(
            export_service.export_campaigns_pdf,
            campaigns,
            current_user.id
        )
        
        return {
            "message": f"{len(campaigns)}개 캠페인 데이터의 PDF 리포트 생성을 시작했습니다.",
            "total_campaigns": len(campaigns),
            "status": "processing"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"잘못된 날짜 형식입니다: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 내보내기 실패: {str(e)}")

@router.post("/purchase-requests/excel")
async def export_purchase_requests_to_excel(
    background_tasks: BackgroundTasks,
    status_filter: Optional[str] = Query(None, description="상태 필터"),
    urgency_filter: Optional[str] = Query(None, description="긴급도 필터"),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    구매요청 데이터를 Excel로 내보내기
    
    - **status_filter**: 상태 필터 (선택사항)
    - **urgency_filter**: 긴급도 필터 (선택사항)
    - **date_from**: 조회 시작일 (선택사항)
    - **date_to**: 조회 종료일 (선택사항)
    """
    try:
        # 구매요청 조회 쿼리 구성
        query = select(PurchaseRequest)
        
        if status_filter:
            query = query.where(PurchaseRequest.status == status_filter)
        
        if urgency_filter:
            query = query.where(PurchaseRequest.urgency == urgency_filter)
        
        if date_from:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.where(PurchaseRequest.created_at >= start_date)
        
        if date_to:
            end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.where(PurchaseRequest.created_at < end_date)
        
        result = await db.execute(query)
        requests = result.scalars().all()
        
        if not requests:
            raise HTTPException(status_code=404, detail="내보낼 구매요청 데이터가 없습니다.")
        
        # 백그라운드에서 Excel 파일 생성
        background_tasks.add_task(
            export_service.export_purchase_requests_excel,
            requests,
            current_user.id
        )
        
        return {
            "message": f"{len(requests)}개 구매요청 데이터의 Excel 내보내기를 시작했습니다.",
            "total_requests": len(requests),
            "status": "processing"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"잘못된 날짜 형식입니다: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel 내보내기 실패: {str(e)}")

@router.post("/dashboard/report")
async def export_dashboard_report(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    대시보드 종합 리포트 PDF 생성
    """
    try:
        # 관리자 권한 확인
        if current_user.role not in ["admin", "슈퍼 어드민", "대행사 어드민"]:
            raise HTTPException(status_code=403, detail="리포트 생성 권한이 없습니다.")
        
        # 대시보드 데이터 수집
        dashboard_data = await collect_dashboard_data(db)
        
        # 백그라운드에서 PDF 리포트 생성
        background_tasks.add_task(
            export_service.create_dashboard_report_pdf,
            dashboard_data,
            current_user.id
        )
        
        return {
            "message": "대시보드 종합 리포트 생성을 시작했습니다.",
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리포트 생성 실패: {str(e)}")

@router.get("/files")
async def list_export_files(
    current_user: User = Depends(get_current_active_user)
):
    """
    생성된 내보내기 파일 목록 조회
    """
    try:
        export_dir = export_service.export_dir
        files = []
        
        if export_dir.exists():
            for file_path in export_dir.glob('*'):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    stat = file_path.stat()
                    files.append({
                        'filename': file_path.name,
                        'size': stat.st_size,
                        'size_mb': round(stat.st_size / (1024 * 1024), 2),
                        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
        
        # 수정 시간 기준 내림차순 정렬
        files.sort(key=lambda x: x['modified_at'], reverse=True)
        
        return {
            "files": files,
            "total": len(files)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 목록 조회 실패: {str(e)}")

@router.get("/download/{filename}")
async def download_export_file(
    filename: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    내보내기 파일 다운로드
    
    - **filename**: 다운로드할 파일명
    """
    try:
        file_path = export_service.export_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        
        # 파일 확장자에 따른 미디어 타입 설정
        if filename.endswith('.xlsx'):
            media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif filename.endswith('.pdf'):
            media_type = 'application/pdf'
        elif filename.endswith('.csv'):
            media_type = 'text/csv'
        else:
            media_type = 'application/octet-stream'
        
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type=media_type
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 다운로드 실패: {str(e)}")

@router.delete("/files/{filename}")
async def delete_export_file(
    filename: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    내보내기 파일 삭제 (관리자 전용)
    
    - **filename**: 삭제할 파일명
    """
    try:
        # 관리자 권한 확인
        if current_user.role not in ["admin", "슈퍼 어드민"]:
            raise HTTPException(status_code=403, detail="파일 삭제 권한이 없습니다.")
        
        file_path = export_service.export_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        
        file_path.unlink()
        
        await manager.send_to_user(current_user.id, {
            "type": "file_delete_success",
            "title": "파일 삭제 완료",
            "message": f"내보내기 파일 '{filename}'이 삭제되었습니다."
        })
        
        return {"message": "파일이 성공적으로 삭제되었습니다."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 삭제 실패: {str(e)}")

@router.post("/cleanup")
async def cleanup_old_export_files(
    days: int = Query(7, ge=1, le=365, description="삭제할 파일의 경과 일수"),
    current_user: User = Depends(get_current_active_user)
):
    """
    오래된 내보내기 파일 정리 (관리자 전용)
    
    - **days**: 경과 일수 (기본값: 7일)
    """
    try:
        # 관리자 권한 확인
        if current_user.role not in ["admin", "슈퍼 어드민"]:
            raise HTTPException(status_code=403, detail="파일 정리 권한이 없습니다.")
        
        deleted_count = await export_service.cleanup_old_exports(days)
        
        await manager.send_to_role("admin", {
            "type": "export_cleanup_complete",
            "title": "내보내기 파일 정리 완료",
            "message": f"{deleted_count}개의 오래된 내보내기 파일이 삭제되었습니다."
        })
        
        return {
            "message": f"{deleted_count}개의 오래된 파일이 정리되었습니다.",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 정리 실패: {str(e)}")

async def collect_dashboard_data(db: AsyncSession) -> dict:
    """대시보드 데이터 수집"""
    # 캠페인 통계
    campaigns_result = await db.execute(select(Campaign))
    campaigns = campaigns_result.scalars().all()
    
    active_campaigns = len([c for c in campaigns if c.status == 'ACTIVE'])
    completed_campaigns = len([c for c in campaigns if c.status == 'COMPLETED'])
    total_budget = sum(c.budget or 0 for c in campaigns)
    
    # 구매요청 통계
    requests_result = await db.execute(select(PurchaseRequest))
    requests = requests_result.scalars().all()
    
    pending_requests = len([r for r in requests if r.status == 'PENDING'])
    
    return {
        "summary": {
            "total_campaigns": len(campaigns),
            "active_campaigns": active_campaigns,
            "completed_campaigns": completed_campaigns,
            "total_budget": total_budget,
            "total_requests": len(requests),
            "pending_requests": pending_requests
        },
        "recent_activities": [
            {"description": f"캠페인 '{campaign.name}' 생성", "timestamp": campaign.created_at}
            for campaign in sorted(campaigns, key=lambda x: x.created_at or datetime.min, reverse=True)[:5]
        ],
        "performance_metrics": {
            "campaign_completion_rate": {
                "value": f"{completed_campaigns/len(campaigns)*100:.1f}%" if campaigns else "0%",
                "status": "healthy"
            },
            "average_budget": {
                "value": f"{total_budget/len(campaigns):,.0f}원" if campaigns else "0원",
                "status": "healthy"
            },
            "pending_request_rate": {
                "value": f"{pending_requests/len(requests)*100:.1f}%" if requests else "0%",
                "status": "warning" if pending_requests/len(requests) > 0.3 else "healthy" if requests else "healthy"
            }
        }
    }