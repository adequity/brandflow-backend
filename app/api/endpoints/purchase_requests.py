from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from urllib.parse import unquote
from datetime import datetime
import os
import uuid
from PIL import Image
import io

from app.db.database import get_async_db
from app.schemas.purchase_request import PurchaseRequestCreate, PurchaseRequestUpdate, PurchaseRequestResponse
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.purchase_request import PurchaseRequest, RequestStatus
from app.core.websocket import manager
from app.services.export_service import export_service

router = APIRouter()


@router.get("/", response_model=dict)
@router.get("", response_model=dict)  #  슬래시 없는 URL도 허용 (Mixed Content 방지)
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
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
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

        # JWT 방식과 동일한 조회 로직 적용
        query = select(PurchaseRequest)

        # 역할별 필터링
        if user_role == 'CLIENT':
            raise HTTPException(status_code=403, detail="고객사는 구매요청에 접근할 수 없습니다.")
        elif user_role == 'STAFF':
            query = query.where(PurchaseRequest.requester_id == current_user.id)
        elif user_role == 'TEAM_LEADER':
            staff_query = select(User.id).where(
                User.team_leader_id == current_user.id,
                User.company == current_user.company
            )
            staff_result = await db.execute(staff_query)
            staff_ids = [row[0] for row in staff_result.all()]

            # 본인이 작성한 것도 포함
            staff_ids.append(current_user.id)

            query = query.where(
                PurchaseRequest.company == current_user.company,
                PurchaseRequest.requester_id.in_(staff_ids)
            )
        elif user_role == 'AGENCY_ADMIN':
            query = query.where(PurchaseRequest.company == current_user.company)
        # SUPER_ADMIN은 모든 요청 조회 가능

        # 상태 필터링
        if status:
            try:
                status_enum = RequestStatus(status)
                query = query.where(PurchaseRequest.status == status_enum)
            except ValueError:
                pass

        # 지출 카테고리 필터링
        if resourceType:
            query = query.where(PurchaseRequest.resource_type == resourceType)

        # 전체 개수 조회
        count_query = select(func.count(PurchaseRequest.id))
        if user_role == 'STAFF':
            count_query = count_query.where(PurchaseRequest.requester_id == current_user.id)
        elif user_role == 'TEAM_LEADER':
            # staff_ids에는 이미 current_user.id가 포함되어 있음 (line 76)
            count_query = count_query.where(
                PurchaseRequest.company == current_user.company,
                PurchaseRequest.requester_id.in_(staff_ids)
            )
        elif user_role == 'AGENCY_ADMIN':
            count_query = count_query.where(PurchaseRequest.company == current_user.company)

        if status:
            try:
                status_enum = RequestStatus(status)
                count_query = count_query.where(PurchaseRequest.status == status_enum)
            except ValueError:
                pass
        if resourceType:
            count_query = count_query.where(PurchaseRequest.resource_type == resourceType)

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # 페이지네이션
        offset = (page - 1) * limit
        paginated_query = query.offset(offset).limit(limit).order_by(PurchaseRequest.created_at.desc())

        result = await db.execute(paginated_query)
        requests = result.scalars().all()

        # 응답 데이터 구성 (requester 정보 포함)
        requests_data = []
        for req in requests:
            # requester 정보 조회
            requester_query = select(User).where(User.id == req.requester_id)
            requester_result = await db.execute(requester_query)
            requester = requester_result.scalar_one_or_none()

            request_data = {
                "id": req.id,
                "title": req.title,
                "description": req.description,
                "amount": req.amount,
                "quantity": req.quantity,
                "vendor": req.vendor,
                "resourceType": req.resource_type,
                "priority": req.priority,
                "dueDate": req.due_date.isoformat() if req.due_date else None,
                "receiptFileUrl": req.receipt_file_url,
                "attachmentUrls": req.attachment_urls,
                "status": req.status.value,
                "campaign_id": req.campaign_id,
                "requester_id": req.requester_id,
                "requester": {
                    "id": requester.id,
                    "name": requester.name,
                    "email": requester.email
                } if requester else None,
                "created_at": req.created_at.isoformat() if req.created_at else None,
                "updated_at": req.updated_at.isoformat() if req.updated_at else None
            }
            requests_data.append(request_data)

        total_pages = (total + limit - 1) // limit

        return {
            "requests": requests_data,
            "total": total,
            "page": page,
            "totalPages": total_pages
        }
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = jwt_user
        print(f"[PURCHASE-REQUESTS-LIST-JWT] Request from user_id={current_user.id}, user_role={current_user.role}")
        
        try:
            # JWT 기반 구매요청 목록 조회
            query = select(PurchaseRequest)
            
            # 역할별 필터링
            if current_user.role.value == 'CLIENT':
                # 클라이언트는 구매요청 접근 불가 (회사 운영비 관련으로 고객사는 무관)
                raise HTTPException(status_code=403, detail="고객사는 구매요청에 접근할 수 없습니다.")
            elif current_user.role.value == 'STAFF':
                # 직원은 자신이 요청한 것만 조회
                query = query.where(PurchaseRequest.requester_id == current_user.id)
            elif current_user.role.value == 'TEAM_LEADER':
                # 팀장은 같은 company의 자신의 팀원들이 작성한 구매요청 조회 가능
                # company로 필터링 + 팀원 ID로 필터링
                staff_query = select(User.id).where(
                    User.team_leader_id == current_user.id,
                    User.company == current_user.company
                )
                staff_result = await db.execute(staff_query)
                staff_ids = [row[0] for row in staff_result.all()]

                # 본인이 작성한 것도 포함
                staff_ids.append(current_user.id)

                query = query.where(
                    PurchaseRequest.company == current_user.company,
                    PurchaseRequest.requester_id.in_(staff_ids)
                )
            elif current_user.role.value == 'AGENCY_ADMIN':
                # AGENCY_ADMIN은 본인 company의 모든 구매요청 조회 가능 (company 컬럼으로 직접 필터링)
                query = query.where(PurchaseRequest.company == current_user.company)
            # SUPER_ADMIN은 모든 요청 조회 가능 (필터링 없음)
            
            # 상태 필터링
            if status:
                try:
                    status_enum = RequestStatus(status)
                    query = query.where(PurchaseRequest.status == status_enum)
                except ValueError:
                    pass  # 잘못된 상태값은 무시

            # 지출 카테고리 필터링
            if resourceType:
                query = query.where(PurchaseRequest.resource_type == resourceType)

            # 전체 개수 조회
            count_query = select(func.count(PurchaseRequest.id))

            # 역할별 필터링 적용 (동일한 로직 사용)
            if current_user.role.value == 'STAFF':
                count_query = count_query.where(PurchaseRequest.requester_id == current_user.id)
            elif current_user.role.value == 'TEAM_LEADER':
                # staff_ids에는 이미 current_user.id가 포함되어 있음 (line 188)
                count_query = count_query.where(
                    PurchaseRequest.company == current_user.company,
                    PurchaseRequest.requester_id.in_(staff_ids)
                )
            elif current_user.role.value == 'AGENCY_ADMIN':
                count_query = count_query.where(PurchaseRequest.company == current_user.company)

            if status:
                try:
                    status_enum = RequestStatus(status)
                    count_query = count_query.where(PurchaseRequest.status == status_enum)
                except ValueError:
                    pass
            if resourceType:
                count_query = count_query.where(PurchaseRequest.resource_type == resourceType)
            
            total_result = await db.execute(count_query)
            total = total_result.scalar()
            
            # 페이지네이션 적용
            offset = (page - 1) * limit
            paginated_query = query.offset(offset).limit(limit).order_by(PurchaseRequest.created_at.desc())
            
            result = await db.execute(paginated_query)
            requests = result.scalars().all()
            
            # 응답 데이터 구성
            requests_data = []
            for req in requests:
                request_data = {
                    "id": req.id,
                    "title": req.title,
                    "description": req.description,
                    "amount": req.amount,
                    "quantity": req.quantity,
                    "vendor": req.vendor,
                    "resourceType": req.resource_type,  # 지출 카테고리
                    "receiptFileUrl": req.receipt_file_url,  # 영수증 파일 URL
                    "attachmentUrls": req.attachment_urls,  # 첨부파일 URLs (JSON)
                    "status": req.status.value,
                    "campaign_id": req.campaign_id,
                    "requester_id": req.requester_id,
                    "created_at": req.created_at.isoformat() if req.created_at else None,
                    "updated_at": req.updated_at.isoformat() if req.updated_at else None
                }
                requests_data.append(request_data)
            
            total_pages = (total + limit - 1) // limit
            
            print(f"[PURCHASE-REQUESTS-LIST-JWT] Found {len(requests)} requests (page {page}/{total_pages}, total: {total})")
            
            return {
                "requests": requests_data,
                "total": total,
                "page": page,
                "totalPages": total_pages
            }
            
        except Exception as e:
            print(f"[PURCHASE-REQUESTS-LIST-JWT] Unexpected error: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"구매요청 조회 중 오류: {str(e)}")


@router.post("/", response_model=PurchaseRequestResponse)
@router.post("", response_model=PurchaseRequestResponse)  # 슬래시 없는 URL도 허용
async def create_purchase_request(
    request_data: PurchaseRequestCreate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """새 구매요청 생성"""
    # 🔍 프론트엔드에서 보낸 데이터 로그
    print(f"[PURCHASE-REQUEST-CREATE] Received data:")
    print(f"  - title: {request_data.title}")
    print(f"  - description: {request_data.description}")
    print(f"  - amount: {request_data.amount}")
    print(f"  - quantity: {request_data.quantity}")
    print(f"  - vendor: {request_data.vendor}")
    print(f"  - resource_type: {request_data.resource_type}")
    print(f"  - priority: {request_data.priority}")
    print(f"  - due_date: {request_data.due_date}")
    print(f"  - campaign_id: {request_data.campaign_id}")

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

        print(f"[PURCHASE-REQUEST-CREATE] Node.js API mode - user_id={user_id}, company={requester.company}")

        # 새 구매요청 생성
        new_request = PurchaseRequest(
            title=request_data.title,
            description=request_data.description,
            amount=request_data.amount,
            quantity=request_data.quantity,
            vendor=request_data.vendor,
            resource_type=request_data.resource_type,  # 지출 카테고리
            priority=request_data.priority,  # 우선순위
            due_date=request_data.due_date,  # 희망 완료일
            status=RequestStatus.PENDING,
            campaign_id=request_data.campaign_id,
            requester_id=user_id,
            company=requester.company  # ✅ 요청자의 company 자동 복사
        )
        
        db.add(new_request)
        await db.commit()
        await db.refresh(new_request)
        
        return new_request
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = jwt_user
        print(f"[PURCHASE-REQUEST-CREATE-JWT] Request from user_id={current_user.id}, user_role={current_user.role}")
        
        try:
            # JWT 기반 구매요청 생성
            new_request = PurchaseRequest(
                title=request_data.title,
                description=request_data.description,
                amount=request_data.amount,
                quantity=request_data.quantity,
                vendor=request_data.vendor,
                resource_type=request_data.resource_type,  # 지출 카테고리
                priority=request_data.priority,  # 우선순위
                due_date=request_data.due_date,  # 희망 완료일
                status=RequestStatus.PENDING,
                campaign_id=request_data.campaign_id,
                requester_id=current_user.id,
                company=current_user.company  # 요청자의 company 자동 복사
            )

            db.add(new_request)
            await db.commit()
            await db.refresh(new_request)

            print(f"[PURCHASE-REQUEST-CREATE-JWT] SUCCESS: Created request {new_request.id} for user {current_user.id}")
            return new_request

        except Exception as e:
            print(f"[PURCHASE-REQUEST-CREATE-JWT] Unexpected error: {type(e).__name__}: {e}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"구매요청 생성 중 오류: {str(e)}")


@router.put("/{request_id}", response_model=PurchaseRequestResponse)
async def update_purchase_request(
    request_id: int,
    request_data: PurchaseRequestUpdate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
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
        is_agency_admin = user_role in ['AGENCY_ADMIN', '대행사 어드민']
        is_staff = user_role in ['STAFF', '직원']

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
        current_user = jwt_user
        print(f"[PURCHASE-REQUEST-UPDATE-JWT] Request from user_id={current_user.id}, user_role={current_user.role}")
        
        try:
            # 구매요청 찾기
            request_query = select(PurchaseRequest).where(PurchaseRequest.id == request_id)
            result = await db.execute(request_query)
            purchase_request = result.scalar_one_or_none()
            
            if not purchase_request:
                raise HTTPException(status_code=404, detail="구매요청을 찾을 수 없습니다.")
            
            # 권한 확인
            if current_user.role.value == 'CLIENT':
                raise HTTPException(status_code=403, detail="고객사는 구매요청에 접근할 수 없습니다.")
            elif current_user.role.value == 'STAFF':
                # STAFF는 자신이 생성한 구매요청만 수정 가능
                if purchase_request.requester_id != current_user.id:
                    raise HTTPException(status_code=403, detail="자신이 생성한 구매요청만 수정할 수 있습니다.")
            elif current_user.role.value == 'TEAM_LEADER':
                # TEAM_LEADER는 조회만 가능, 수정/삭제 불가능
                raise HTTPException(status_code=403, detail="팀장은 구매요청을 조회만 가능하며 수정할 수 없습니다.")
            elif current_user.role.value == 'AGENCY_ADMIN':
                # AGENCY_ADMIN은 본인 company의 모든 구매요청 수정/삭제 가능 (company 컬럼으로 직접 체크)
                if purchase_request.company != current_user.company:
                    raise HTTPException(status_code=403, detail="본인 회사의 구매요청만 수정할 수 있습니다.")
            # SUPER_ADMIN은 모든 요청 수정 가능 (체크 없음)
            
            # 상태 업데이트
            update_data = request_data.model_dump(exclude_unset=True)
            old_status = purchase_request.status
            
            for field, value in update_data.items():
                if hasattr(purchase_request, field):
                    setattr(purchase_request, field, value)
            
            await db.commit()
            await db.refresh(purchase_request)
            
            # 상태가 변경된 경우 WebSocket 알림 전송
            if 'status' in update_data and old_status != purchase_request.status:
                await manager.notify_purchase_request(
                    request_id=purchase_request.id,
                    status=purchase_request.status,
                    user_id=purchase_request.requester_id
                )
            
            print(f"[PURCHASE-REQUEST-UPDATE-JWT] SUCCESS: Updated request {request_id} by user {current_user.id}")
            return purchase_request
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"[PURCHASE-REQUEST-UPDATE-JWT] Unexpected error: {type(e).__name__}: {e}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"구매요청 수정 중 오류: {str(e)}")


@router.get("/summary/stats")
async def get_purchase_request_stats(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    # 월간 필터 (YYYY-MM 형식)
    month: Optional[str] = Query(None, description="월간 필터 (YYYY-MM)"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """구매요청 통계 데이터 조회 (월간 필터 지원)"""
    
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
        current_user = jwt_user
        print(f"[PURCHASE-REQUEST-STATS-JWT] Request from user_id={current_user.id}, user_role={current_user.role}, month={month}")

        try:
            # 월간 필터 파싱
            month_filter = None
            if month:
                try:
                    year, month_num = month.split('-')
                    year = int(year)
                    month_num = int(month_num)
                    # 해당 월의 시작일과 종료일 계산
                    from calendar import monthrange
                    _, last_day = monthrange(year, month_num)
                    start_date = datetime(year, month_num, 1)
                    end_date = datetime(year, month_num, last_day, 23, 59, 59)
                    month_filter = (start_date, end_date)
                    print(f"[PURCHASE-REQUEST-STATS-JWT] Month filter: {start_date.isoformat()} to {end_date.isoformat()}")
                except (ValueError, AttributeError) as e:
                    print(f"[PURCHASE-REQUEST-STATS-JWT] Invalid month format: {month}, error: {e}")
                    raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM format.")

            # 권한에 따라 데이터 필터링
            query = select(PurchaseRequest)

            if current_user.role.value == 'CLIENT':
                # 클라이언트는 구매요청 접근 불가
                raise HTTPException(status_code=403, detail="고객사는 구매요청 통계에 접근할 수 없습니다.")
            elif current_user.role.value == 'STAFF':
                # 직원은 자신의 요청만
                query = query.where(PurchaseRequest.requester_id == current_user.id)
            elif current_user.role.value == 'TEAM_LEADER':
                # 팀장은 자신의 팀원들 요청 + 본인 요청 조회
                staff_query = select(User.id).where(
                    User.team_leader_id == current_user.id,
                    User.company == current_user.company
                )
                staff_result = await db.execute(staff_query)
                staff_ids = [row[0] for row in staff_result.all()]

                # 본인이 작성한 것도 포함
                staff_ids.append(current_user.id)

                query = query.where(PurchaseRequest.requester_id.in_(staff_ids))
            elif current_user.role.value == 'AGENCY_ADMIN':
                # AGENCY_ADMIN은 본인 company의 모든 요청 (company 컬럼으로 직접 필터링)
                query = query.where(PurchaseRequest.company == current_user.company)
            # SUPER_ADMIN은 모든 데이터

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

            # 권한별 필터링 적용
            if current_user.role.value == 'STAFF':
                user_filter = PurchaseRequest.requester_id == current_user.id
                total_query = total_query.where(user_filter)
                pending_query = pending_query.where(user_filter)
                approved_query = approved_query.where(user_filter)
                rejected_query = rejected_query.where(user_filter)
                completed_query = completed_query.where(user_filter)
                total_amount_query = total_amount_query.where(user_filter)
                approved_amount_query = approved_amount_query.where(user_filter)
            elif current_user.role.value == 'TEAM_LEADER':
                # staff_ids는 위에서 이미 조회되었으므로 재사용 (line 609에서 current_user.id 포함됨)
                team_filter = PurchaseRequest.requester_id.in_(staff_ids)

                total_query = total_query.where(team_filter)
                pending_query = pending_query.where(team_filter)
                approved_query = approved_query.where(team_filter)
                rejected_query = rejected_query.where(team_filter)
                completed_query = completed_query.where(team_filter)
                total_amount_query = total_amount_query.where(team_filter)
                approved_amount_query = approved_amount_query.where(team_filter)
            elif current_user.role.value == 'AGENCY_ADMIN':
                # 같은 company의 모든 요청 (company 컬럼으로 직접 필터링)
                company_filter = PurchaseRequest.company == current_user.company

                total_query = total_query.where(company_filter)
                pending_query = pending_query.where(company_filter)
                approved_query = approved_query.where(company_filter)
                rejected_query = rejected_query.where(company_filter)
                completed_query = completed_query.where(company_filter)
                total_amount_query = total_amount_query.where(company_filter)
                approved_amount_query = approved_amount_query.where(company_filter)

            # 월간 필터 적용
            if month_filter:
                start_date, end_date = month_filter
                date_filter = (PurchaseRequest.created_at >= start_date) & (PurchaseRequest.created_at <= end_date)
                total_query = total_query.where(date_filter)
                pending_query = pending_query.where(date_filter)
                approved_query = approved_query.where(date_filter)
                rejected_query = rejected_query.where(date_filter)
                completed_query = completed_query.where(date_filter)
                total_amount_query = total_amount_query.where(date_filter)
                approved_amount_query = approved_amount_query.where(date_filter)
            
            # 쿼리 실행
            total_count = await db.scalar(total_query)
            pending_count = await db.scalar(pending_query)
            approved_count = await db.scalar(approved_query)
            rejected_count = await db.scalar(rejected_query)
            completed_count = await db.scalar(completed_query)
            
            total_amount = await db.scalar(total_amount_query)
            approved_amount = await db.scalar(approved_amount_query)
            
            print(f"[PURCHASE-REQUEST-STATS-JWT] SUCCESS: Returning stats for user {current_user.id}")
            
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
            
        except Exception as e:
            print(f"[PURCHASE-REQUEST-STATS-JWT] Unexpected error: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"통계 조회 중 오류: {str(e)}")


@router.post("/{request_id}/receipt")
async def upload_receipt_new(
    request_id: int,
    receipt: UploadFile = File(...),
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """구매요청 영수증 첨부 (로고 방식과 동일)"""
    from app.core.file_upload import file_manager

    # Node.js API 호환 모드인지 확인
    if viewerId is not None:
        user_id = viewerId
        user_role = viewerRole

        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")

        # URL 디코딩
        user_role = unquote(user_role).strip()

        print(f"[RECEIPT-UPLOAD] Node.js mode - user_id={user_id}, role={user_role}, filename={receipt.filename}")

        # 구매요청 찾기
        query = select(PurchaseRequest).where(PurchaseRequest.id == request_id)
        result = await db.execute(query)
        purchase_request = result.scalar_one_or_none()

        if not purchase_request:
            raise HTTPException(status_code=404, detail="구매요청을 찾을 수 없습니다.")

        # 권한 확인
        is_agency_admin = user_role in ['AGENCY_ADMIN', '대행사 어드민']
        is_staff = user_role in ['STAFF', '직원']
        is_requester = purchase_request.requester_id == user_id

        if not (is_agency_admin or (is_staff and is_requester)):
            raise HTTPException(status_code=403, detail="권한이 없습니다.")

        # 파일 업로드 (file_manager 사용)
        file_result = await file_manager.save_file(receipt)
        receipt_url = file_result["url"]

        # 영수증 URL 업데이트
        purchase_request.receipt_file_url = receipt_url
        await db.commit()
        await db.refresh(purchase_request)

        print(f"[RECEIPT-UPLOAD] SUCCESS: Saved receipt for request {request_id}, URL: {receipt_url}")

        return {
            "success": True,
            "fileUrl": receipt_url,
            "message": "영수증이 업로드되었습니다."
        }
    else:
        # JWT 토큰 기반
        current_user = jwt_user
        print(f"[RECEIPT-UPLOAD] JWT mode - user_id={current_user.id}, filename={receipt.filename}")

        # 구매요청 찾기
        query = select(PurchaseRequest).where(PurchaseRequest.id == request_id)
        result = await db.execute(query)
        purchase_request = result.scalar_one_or_none()

        if not purchase_request:
            raise HTTPException(status_code=404, detail="구매요청을 찾을 수 없습니다.")

        # 권한 확인
        is_agency_admin = current_user.role.value == 'AGENCY_ADMIN'
        is_requester = purchase_request.requester_id == current_user.id

        if not (is_agency_admin or is_requester):
            raise HTTPException(status_code=403, detail="권한이 없습니다.")

        # 파일 업로드 (file_manager 사용)
        file_result = await file_manager.save_file(receipt)
        receipt_url = file_result["url"]

        # 영수증 URL 업데이트
        purchase_request.receipt_file_url = receipt_url
        await db.commit()
        await db.refresh(purchase_request)

        print(f"[RECEIPT-UPLOAD] SUCCESS: Saved receipt for request {request_id}, URL: {receipt_url}")

        return {
            "success": True,
            "fileUrl": receipt_url,
            "message": "영수증이 업로드되었습니다."
        }


@router.post("/{request_id}/upload-receipt")
async def upload_receipt_legacy(
    request_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """영수증 파일 업로드 (구버전 - 호환성 유지용)"""
    print(f"[RECEIPT-UPLOAD-LEGACY] Request from user_id={current_user.id}, request_id={request_id}, filename={file.filename}")

    try:
        # 구매요청 찾기
        request_query = select(PurchaseRequest).where(PurchaseRequest.id == request_id)
        result = await db.execute(request_query)
        purchase_request = result.scalar_one_or_none()

        if not purchase_request:
            raise HTTPException(status_code=404, detail="구매요청을 찾을 수 없습니다.")

        # 권한 확인
        if current_user.role.value == 'CLIENT':
            raise HTTPException(status_code=403, detail="고객사는 구매요청에 접근할 수 없습니다.")
        elif current_user.role.value == 'STAFF':
            if purchase_request.requester_id != current_user.id:
                raise HTTPException(status_code=403, detail="자신이 생성한 구매요청만 수정할 수 있습니다.")
        elif current_user.role.value == 'TEAM_LEADER':
            raise HTTPException(status_code=403, detail="팀장은 구매요청을 조회만 가능하며 수정할 수 없습니다.")
        elif current_user.role.value == 'AGENCY_ADMIN':
            # AGENCY_ADMIN은 본인 company의 구매요청만 수정 가능 (company 컬럼으로 직접 체크)
            if purchase_request.company != current_user.company:
                raise HTTPException(status_code=403, detail="본인 회사의 구매요청만 수정할 수 있습니다.")
        # SUPER_ADMIN은 모든 요청 수정 가능

        # 파일 확장자 검증
        allowed_extensions = ['jpg', 'jpeg', 'png']
        file_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else ''

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 파일 형식입니다. jpg, jpeg, png 파일만 업로드 가능합니다."
            )

        # 파일 읽기
        contents = await file.read()

        # 이미지 검증 및 리사이징 (모바일 최적화)
        try:
            image = Image.open(io.BytesIO(contents))

            # EXIF 회전 정보 처리
            try:
                from PIL import ExifTags
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == 'Orientation':
                        break
                exif = image._getexif()
                if exif is not None:
                    orientation_value = exif.get(orientation)
                    if orientation_value == 3:
                        image = image.rotate(180, expand=True)
                    elif orientation_value == 6:
                        image = image.rotate(270, expand=True)
                    elif orientation_value == 8:
                        image = image.rotate(90, expand=True)
            except (AttributeError, KeyError, IndexError):
                pass

            # 이미지 리사이징 (최대 1920px 너비)
            max_width = 1920
            if image.width > max_width:
                ratio = max_width / image.width
                new_height = int(image.height * ratio)
                image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
                print(f"[RECEIPT-UPLOAD] Resized image from {image.width}x{image.height} to {max_width}x{new_height}")

            # RGB 변환 (PNG 투명도 처리)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background

            # 최적화된 이미지를 바이트로 저장
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=85, optimize=True)
            optimized_contents = output.getvalue()

        except Exception as img_error:
            print(f"[RECEIPT-UPLOAD] Image processing error: {img_error}")
            raise HTTPException(status_code=400, detail="유효하지 않은 이미지 파일입니다.")

        # Railway Volume 저장 경로 설정
        upload_dir = "/app/uploads/receipts"
        os.makedirs(upload_dir, exist_ok=True)

        # 고유 파일명 생성 (UUID + timestamp)
        file_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file_id}.jpg"
        file_path = os.path.join(upload_dir, filename)

        # 파일 저장
        with open(file_path, "wb") as f:
            f.write(optimized_contents)

        # 파일 URL 생성 (Railway 배포 URL 기준)
        file_url = f"/uploads/receipts/{filename}"

        # DB 업데이트
        purchase_request.receipt_file_url = file_url
        purchase_request.updated_at = datetime.now()

        await db.commit()
        await db.refresh(purchase_request)

        print(f"[RECEIPT-UPLOAD] SUCCESS: Saved {filename} for request {request_id}")

        return {
            "success": True,
            "fileUrl": file_url,
            "filename": filename,
            "message": "영수증이 업로드되었습니다."
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[RECEIPT-UPLOAD] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"파일 업로드 중 오류: {str(e)}")


@router.delete("/{request_id}")
async def delete_purchase_request(
    request_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """구매요청 삭제"""
    # JWT 기반 또는 Node.js API 호환 모드
    if viewerId is not None:
        user_id = viewerId
        user_role = unquote(viewerRole).strip() if viewerRole else None

        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")

        # 사용자 조회
        user_query = select(User).where(User.id == user_id)
        result = await db.execute(user_query)
        current_user = result.scalar_one_or_none()

        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    else:
        current_user = jwt_user

    print(f"[PURCHASE-REQUEST-DELETE] Request from user_id={current_user.id}, user_role={current_user.role}")

    try:
        # 구매요청 찾기
        request_query = select(PurchaseRequest).where(PurchaseRequest.id == request_id)
        result = await db.execute(request_query)
        purchase_request = result.scalar_one_or_none()

        if not purchase_request:
            raise HTTPException(status_code=404, detail="구매요청을 찾을 수 없습니다.")

        # 권한 확인
        if current_user.role.value == 'CLIENT':
            raise HTTPException(status_code=403, detail="고객사는 구매요청에 접근할 수 없습니다.")
        elif current_user.role.value == 'STAFF':
            # STAFF는 자신이 생성한 구매요청만 삭제 가능
            if purchase_request.requester_id != current_user.id:
                raise HTTPException(status_code=403, detail="자신이 생성한 구매요청만 삭제할 수 있습니다.")
        elif current_user.role.value == 'TEAM_LEADER':
            # TEAM_LEADER는 조회만 가능, 수정/삭제 불가능
            raise HTTPException(status_code=403, detail="팀장은 구매요청을 조회만 가능하며 삭제할 수 없습니다.")
        elif current_user.role.value == 'AGENCY_ADMIN':
            # AGENCY_ADMIN은 본인 company의 모든 구매요청 삭제 가능
            if purchase_request.company != current_user.company:
                raise HTTPException(status_code=403, detail="본인 회사의 구매요청만 삭제할 수 있습니다.")
        # SUPER_ADMIN은 모든 요청 삭제 가능

        # 영수증 파일이 있으면 삭제
        if purchase_request.receipt_file_url:
            try:
                file_path = f"/app{purchase_request.receipt_file_url}"
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"[PURCHASE-REQUEST-DELETE] Deleted receipt file: {file_path}")
            except Exception as file_error:
                print(f"[PURCHASE-REQUEST-DELETE] Failed to delete receipt file: {file_error}")
                # 파일 삭제 실패는 무시하고 계속 진행

        # DB에서 삭제
        await db.delete(purchase_request)
        await db.commit()

        print(f"[PURCHASE-REQUEST-DELETE] SUCCESS: Deleted request {request_id} by user {current_user.id}")

        return {
            "success": True,
            "message": "구매요청이 삭제되었습니다.",
            "deletedId": request_id
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PURCHASE-REQUEST-DELETE] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"구매요청 삭제 중 오류: {str(e)}")


@router.put("/{request_id}/approve")
async def approve_purchase_request(
    request_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """구매요청 승인"""
    # JWT 기반 또는 Node.js API 호환 모드
    if viewerId is not None:
        user_id = viewerId
        user_role = unquote(viewerRole).strip() if viewerRole else None

        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")

        # 사용자 조회
        user_query = select(User).where(User.id == user_id)
        result = await db.execute(user_query)
        current_user = result.scalar_one_or_none()

        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    else:
        current_user = jwt_user

    print(f"[PURCHASE-REQUEST-APPROVE] Request from user_id={current_user.id}, user_role={current_user.role}")

    try:
        # 구매요청 찾기
        request_query = select(PurchaseRequest).where(PurchaseRequest.id == request_id)
        result = await db.execute(request_query)
        purchase_request = result.scalar_one_or_none()

        if not purchase_request:
            raise HTTPException(status_code=404, detail="구매요청을 찾을 수 없습니다.")

        # 권한 확인 - AGENCY_ADMIN과 SUPER_ADMIN만 승인 가능
        if current_user.role.value not in ['AGENCY_ADMIN', 'SUPER_ADMIN']:
            raise HTTPException(status_code=403, detail="구매요청 승인은 대행사 어드민 또는 슈퍼 어드민만 가능합니다.")

        if current_user.role.value == 'AGENCY_ADMIN':
            # AGENCY_ADMIN은 본인 company의 구매요청만 승인 가능
            if purchase_request.company != current_user.company:
                raise HTTPException(status_code=403, detail="본인 회사의 구매요청만 승인할 수 있습니다.")

        # 요청자 정보 조회 (문서 생성용)
        requester_query = select(User).where(User.id == purchase_request.requester_id)
        requester_result = await db.execute(requester_query)
        requester = requester_result.scalar_one_or_none()

        # 상태 업데이트
        old_status = purchase_request.status
        purchase_request.status = RequestStatus.APPROVED

        await db.commit()
        await db.refresh(purchase_request)

        # 지출품의서 PDF 자동 생성
        document_url = None
        try:
            document_path = await export_service.generate_purchase_request_document(
                purchase_request=purchase_request,
                requester=requester,
                approver=current_user
            )
            # 상대 경로로 변환 (예: ./exports/purchase_request_1_20250130_123456.pdf -> /exports/purchase_request_1_20250130_123456.pdf)
            document_url = document_path.replace('./exports', '/exports')
            print(f"[PURCHASE-REQUEST-APPROVE] Document generated: {document_url}")
        except Exception as doc_error:
            # 문서 생성 실패는 로그만 남기고 승인 프로세스는 계속 진행
            print(f"[PURCHASE-REQUEST-APPROVE] Document generation failed: {doc_error}")

        # WebSocket 알림
        await manager.notify_purchase_request(
            request_id=purchase_request.id,
            status=purchase_request.status,
            user_id=purchase_request.requester_id
        )

        print(f"[PURCHASE-REQUEST-APPROVE] SUCCESS: Approved request {request_id} by user {current_user.id}")

        return {
            "success": True,
            "message": "구매요청이 승인되었습니다.",
            "documentUrl": document_url,
            "request": {
                "id": purchase_request.id,
                "title": purchase_request.title,
                "status": purchase_request.status.value,
                "previousStatus": old_status.value
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PURCHASE-REQUEST-APPROVE] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"구매요청 승인 중 오류: {str(e)}")


@router.put("/{request_id}/reject")
async def reject_purchase_request(
    request_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """구매요청 반려"""
    # JWT 기반 또는 Node.js API 호환 모드
    if viewerId is not None:
        user_id = viewerId
        user_role = unquote(viewerRole).strip() if viewerRole else None

        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")

        # 사용자 조회
        user_query = select(User).where(User.id == user_id)
        result = await db.execute(user_query)
        current_user = result.scalar_one_or_none()

        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    else:
        current_user = jwt_user

    print(f"[PURCHASE-REQUEST-REJECT] Request from user_id={current_user.id}, user_role={current_user.role}")

    try:
        # 구매요청 찾기
        request_query = select(PurchaseRequest).where(PurchaseRequest.id == request_id)
        result = await db.execute(request_query)
        purchase_request = result.scalar_one_or_none()

        if not purchase_request:
            raise HTTPException(status_code=404, detail="구매요청을 찾을 수 없습니다.")

        # 권한 확인 - AGENCY_ADMIN과 SUPER_ADMIN만 반려 가능
        if current_user.role.value not in ['AGENCY_ADMIN', 'SUPER_ADMIN']:
            raise HTTPException(status_code=403, detail="구매요청 반려는 대행사 어드민 또는 슈퍼 어드민만 가능합니다.")

        if current_user.role.value == 'AGENCY_ADMIN':
            # AGENCY_ADMIN은 본인 company의 구매요청만 반려 가능
            if purchase_request.company != current_user.company:
                raise HTTPException(status_code=403, detail="본인 회사의 구매요청만 반려할 수 있습니다.")

        # 상태 업데이트
        old_status = purchase_request.status
        purchase_request.status = RequestStatus.REJECTED

        await db.commit()
        await db.refresh(purchase_request)

        # WebSocket 알림
        await manager.notify_purchase_request(
            request_id=purchase_request.id,
            status=purchase_request.status,
            user_id=purchase_request.requester_id
        )

        print(f"[PURCHASE-REQUEST-REJECT] SUCCESS: Rejected request {request_id} by user {current_user.id}")

        return {
            "success": True,
            "message": "구매요청이 반려되었습니다.",
            "request": {
                "id": purchase_request.id,
                "title": purchase_request.title,
                "status": purchase_request.status.value,
                "previousStatus": old_status.value
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PURCHASE-REQUEST-REJECT] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"구매요청 반려 중 오류: {str(e)}")


@router.post("/{request_id}/generate-documents")
async def generate_purchase_request_documents(
    request_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """구매요청 문서 생성 (견적서, 거래명세서 등)"""
    # JWT 기반 또는 Node.js API 호환 모드
    if viewerId is not None:
        user_id = viewerId
        user_role = unquote(viewerRole).strip() if viewerRole else None

        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")

        # 사용자 조회
        user_query = select(User).where(User.id == user_id)
        result = await db.execute(user_query)
        current_user = result.scalar_one_or_none()

        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    else:
        current_user = jwt_user

    print(f"[PURCHASE-REQUEST-GENERATE-DOCS] Request from user_id={current_user.id}, user_role={current_user.role}")

    try:
        # 구매요청 찾기
        request_query = select(PurchaseRequest).where(PurchaseRequest.id == request_id)
        result = await db.execute(request_query)
        purchase_request = result.scalar_one_or_none()

        if not purchase_request:
            raise HTTPException(status_code=404, detail="구매요청을 찾을 수 없습니다.")

        # 권한 확인
        if current_user.role.value == 'CLIENT':
            raise HTTPException(status_code=403, detail="고객사는 구매요청 문서를 생성할 수 없습니다.")
        elif current_user.role.value == 'STAFF':
            if purchase_request.requester_id != current_user.id:
                raise HTTPException(status_code=403, detail="자신이 생성한 구매요청의 문서만 생성할 수 있습니다.")
        elif current_user.role.value == 'TEAM_LEADER':
            raise HTTPException(status_code=403, detail="팀장은 구매요청 문서 생성 권한이 없습니다.")
        elif current_user.role.value == 'AGENCY_ADMIN':
            if purchase_request.company != current_user.company:
                raise HTTPException(status_code=403, detail="본인 회사의 구매요청 문서만 생성할 수 있습니다.")

        # TODO: 실제 문서 생성 로직 구현
        # 현재는 플레이스홀더로 성공 응답만 반환
        print(f"[PURCHASE-REQUEST-GENERATE-DOCS] SUCCESS: Document generation requested for request {request_id}")

        return {
            "success": True,
            "message": "문서 생성 기능은 현재 개발 중입니다.",
            "files": {
                "pdf": None,
                "jpg": None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PURCHASE-REQUEST-GENERATE-DOCS] Unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"문서 생성 중 오류: {str(e)}")