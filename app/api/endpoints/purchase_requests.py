from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from urllib.parse import unquote
from datetime import datetime

from app.db.database import get_async_db
from app.schemas.purchase_request import PurchaseRequestCreate, PurchaseRequestUpdate, PurchaseRequestResponse
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.purchase_request import PurchaseRequest, RequestStatus
from app.core.websocket import manager

router = APIRouter()


@router.get("/", response_model=dict)
@router.get("", response_model=dict)  # 🚨 슬래시 없는 URL도 허용 (Mixed Content 방지)
async def get_purchase_requests(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    # 필터 파라미터
    status: Optional[str] = Query(None),
    resourceType: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db)
):
    """구매요청 목록 조회 (권한별 필터링)"""
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
        
        # 임시로 빈 결과 반환 (테이블에 데이터가 없어 SQL 오류 방지)
        requests = []
        total = 0
        
        return {
            "requests": requests,
            "total": total,
            "page": page,
            "totalPages": (total + limit - 1) // limit
        }
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 구매요청 조회 구현
        return {"requests": [], "total": 0, "page": 1, "totalPages": 0}


@router.post("/", response_model=PurchaseRequestResponse)
async def create_purchase_request(
    request_data: PurchaseRequestCreate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """새 구매요청 생성"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 요청자 정보 확인
        requester_query = select(User).where(User.id == user_id)
        result = await db.execute(requester_query)
        requester = result.scalar_one_or_none()
        
        if not requester:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        # 새 구매요청 생성
        new_request = PurchaseRequest(
            title=request_data.title,
            description=request_data.description,
            amount=request_data.amount,
            quantity=request_data.quantity,
            vendor=request_data.vendor,
            status=RequestStatus.PENDING,
            campaign_id=request_data.campaign_id,
            requester_id=user_id
        )
        
        db.add(new_request)
        await db.commit()
        await db.refresh(new_request)
        
        return new_request
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 구매요청 생성 구현
        raise HTTPException(status_code=501, detail="Not implemented yet")


@router.put("/{request_id}", response_model=PurchaseRequestResponse)
async def update_purchase_request(
    request_id: int,
    request_data: PurchaseRequestUpdate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """구매요청 상태 업데이트"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 구매요청 찾기
        request_query = select(PurchaseRequest).where(PurchaseRequest.id == request_id)
        result = await db.execute(request_query)
        purchase_request = result.scalar_one_or_none()
        
        if not purchase_request:
            raise HTTPException(status_code=404, detail="구매요청을 찾을 수 없습니다.")
        
        # 권한 확인 - 대행사 어드민/직원만 상태 변경 가능
        is_agency_admin = user_role == '대행사 어드민'
        is_staff = user_role == '직원'
        
        if not is_agency_admin and not is_staff:
            raise HTTPException(status_code=403, detail="권한이 없습니다. 대행사 어드민 또는 직원만 구매요청 상태를 변경할 수 있습니다.")
        
        # 상태 업데이트
        update_data = request_data.model_dump(exclude_unset=True)
        old_status = purchase_request.status
        
        for field, value in update_data.items():
            if hasattr(purchase_request, field):
                setattr(purchase_request, field, value)
        
        # updated_at은 TimestampMixin에서 자동 처리됨
        
        await db.commit()
        await db.refresh(purchase_request)
        
        # 상태가 변경된 경우 WebSocket 알림 전송
        if 'status' in update_data and old_status != purchase_request.status:
            await manager.notify_purchase_request(
                request_id=purchase_request.id,
                status=purchase_request.status,
                user_id=purchase_request.requester_id  # 요청자에게 알림
            )
        
        return purchase_request
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 구매요청 업데이트 구현
        raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/summary/stats")
async def get_purchase_request_stats(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """구매요청 통계 데이터 조회"""
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 사용자 정보 조회
        user_query = select(User).where(User.id == user_id)
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 권한에 따라 데이터 필터링
        query = select(PurchaseRequest)
        
        if user_role not in ['슈퍼 어드민']:
            # 슈퍼 어드민이 아니면 자신의 회사 데이터만
            if user.company:
                # 회사 필터링 로직은 실제 스키마에 맞게 조정 필요
                pass
        
        # 상태별 통계
        total_query = select(func.count(PurchaseRequest.id))
        pending_query = select(func.count(PurchaseRequest.id)).where(PurchaseRequest.status == RequestStatus.PENDING)
        approved_query = select(func.count(PurchaseRequest.id)).where(PurchaseRequest.status == RequestStatus.APPROVED)
        rejected_query = select(func.count(PurchaseRequest.id)).where(PurchaseRequest.status == RequestStatus.REJECTED)
        completed_query = select(func.count(PurchaseRequest.id)).where(PurchaseRequest.status == RequestStatus.COMPLETED)
        
        # 총액 통계
        total_amount_query = select(func.coalesce(func.sum(PurchaseRequest.amount), 0))
        approved_amount_query = select(func.coalesce(func.sum(PurchaseRequest.amount), 0)).where(
            PurchaseRequest.status == RequestStatus.APPROVED
        )
        
        # 쿼리 실행
        total_count = await db.scalar(total_query)
        pending_count = await db.scalar(pending_query)
        approved_count = await db.scalar(approved_query)
        rejected_count = await db.scalar(rejected_query)
        completed_count = await db.scalar(completed_query)
        
        total_amount = await db.scalar(total_amount_query)
        approved_amount = await db.scalar(approved_amount_query)
        
        return {
            "totalRequests": total_count or 0,
            "pendingRequests": pending_count or 0,
            "approvedRequests": approved_count or 0,
            "rejectedRequests": rejected_count or 0,
            "completedRequests": completed_count or 0,
            "totalAmount": float(total_amount or 0),
            "approvedAmount": float(approved_amount or 0),
            "averageAmount": float(total_amount / total_count) if total_count > 0 else 0.0,
            "approvalRate": float(approved_count / total_count * 100) if total_count > 0 else 0.0
        }
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        # 기본 통계 반환
        return {
            "totalRequests": 0,
            "pendingRequests": 0,
            "approvedRequests": 0,
            "rejectedRequests": 0,
            "completedRequests": 0,
            "totalAmount": 0.0,
            "approvedAmount": 0.0,
            "averageAmount": 0.0,
            "approvalRate": 0.0
        }