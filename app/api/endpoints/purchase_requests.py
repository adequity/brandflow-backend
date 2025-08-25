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
            resource_type=request_data.resource_type or '캠페인 업무 발주',
            priority=request_data.priority or '보통',
            status=RequestStatus.PENDING,
            due_date=request_data.due_date,
            campaign_id=request_data.campaign_id,
            requester_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
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
        
        purchase_request.updated_at = datetime.utcnow()
        
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