from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import joinedload
from typing import List, Optional
from urllib.parse import unquote
from datetime import datetime, timezone

from app.db.database import get_async_db
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignResponse
from app.schemas.post import PostCreate, PostResponse
from app.schemas.order_request import OrderRequestCreate, OrderRequestResponse
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.models.campaign import Campaign, CampaignStatus
from app.models.post import Post
from app.models.order_request import OrderRequest
from app.models.product import Product
from app.core.websocket import manager

router = APIRouter()


@router.get("/")
async def get_campaigns(
    request: Request,
    # 페이지네이션 파라미터
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(10, ge=1, le=100, description="페이지당 항목 수"),
    # JWT 인증된 사용자
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """캠페인 목록 조회 (JWT 인증 기반 권한별 필터링)"""
    print(f"[CAMPAIGNS-LIST] JWT User: {current_user.name}, Role: {current_user.role.value}, Company: {current_user.company}")
    
    user_id = current_user.id
    user_role = current_user.role.value
    
    # 페이지네이션 처리
    current_page = page
    page_size = size
    offset = (page - 1) * size
    
    print(f"[CAMPAIGNS-LIST] Pagination - page={current_page}, size={page_size}, offset={offset}")
    
    # JWT 기반 권한별 필터링 (UserRole enum 값 사용)
    # 기존 client_company 필드 기반 필터링 (데이터베이스 구조에 맞춰)
    if user_role == UserRole.SUPER_ADMIN.value:
        # 슈퍼 어드민은 모든 캠페인 조회 가능
        query = select(Campaign).options(joinedload(Campaign.creator), joinedload(Campaign.client_user), joinedload(Campaign.posts))
        count_query = select(func.count(Campaign.id))
    elif user_role == UserRole.AGENCY_ADMIN.value:
        # 대행사 어드민은 같은 회사의 캠페인들 조회 가능 (creator의 company 기준)
        query = select(Campaign).options(joinedload(Campaign.creator), joinedload(Campaign.client_user), joinedload(Campaign.posts)).join(User, Campaign.creator_id == User.id).where(
            User.company == current_user.company
        )
        count_query = select(func.count(Campaign.id)).join(User, Campaign.creator_id == User.id).where(
            User.company == current_user.company
        )
    elif user_role == UserRole.CLIENT.value:
        # 클라이언트는 자신을 대상으로 한 캠페인만 조회 가능 (client_user_id 외래키 관계 사용)
        query = select(Campaign).options(
            joinedload(Campaign.creator),
            joinedload(Campaign.client_user),
            joinedload(Campaign.posts)
        ).where(Campaign.client_user_id == user_id)
        count_query = select(func.count(Campaign.id)).where(Campaign.client_user_id == user_id)
    elif user_role == UserRole.STAFF.value:
        # 직원은 자신이 생성한 캠페인만 조회 가능 (creator_id 기준)
        query = select(Campaign).options(joinedload(Campaign.creator), joinedload(Campaign.client_user), joinedload(Campaign.posts)).where(Campaign.creator_id == user_id)
        count_query = select(func.count(Campaign.id)).where(Campaign.creator_id == user_id)
    else:
        # 기본적으로는 같은 회사 기준 필터링 (creator의 company 기준)
        query = select(Campaign).options(joinedload(Campaign.creator), joinedload(Campaign.client_user), joinedload(Campaign.posts)).join(User, Campaign.creator_id == User.id).where(
            User.company == current_user.company
        )
        count_query = select(func.count(Campaign.id)).join(User, Campaign.creator_id == User.id).where(
            User.company == current_user.company
        )
    
    # 전체 개수 조회
    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar()
    
    # 페이지네이션 적용된 쿼리 실행
    paginated_query = query.offset(offset).limit(page_size).order_by(Campaign.created_at.desc())
    result = await db.execute(paginated_query)
    campaigns = result.unique().scalars().all()
    
    # 페이지네이션 메타데이터 계산
    total_pages = (total_count + page_size - 1) // page_size
    has_next = current_page < total_pages
    has_prev = current_page > 1
    
    print(f"[CAMPAIGNS-LIST-JWT] Found {len(campaigns)} campaigns (page {current_page}/{total_pages}, total: {total_count})")
    
    # Campaign 모델을 CampaignResponse 스키마로 직렬화 (기존 구조 유지)
    serialized_campaigns = []
    for campaign in campaigns:
        campaign_data = {
            "id": campaign.id,
            "name": campaign.name,
            "description": campaign.description,
            "status": campaign.status.value if campaign.status else None,
            "client_company": campaign.client_company,
            "budget": campaign.budget,  # budget 필드 추가
            "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
            "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
            "invoiceIssued": getattr(campaign, 'invoice_issued', False) if hasattr(campaign, 'invoice_issued') else False,  # 계산서 발행 완료
            "paymentCompleted": getattr(campaign, 'payment_completed', False) if hasattr(campaign, 'payment_completed') else False,  # 입금 완료
            "creator_id": campaign.creator_id,
            "staff_id": campaign.staff_id,  # 캠페인 담당 직원 ID 추가
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
            "User": {
                "id": campaign.creator.id,
                "name": campaign.creator.name,
                "role": campaign.creator.role.value,
                "company": campaign.creator.company
            } if campaign.creator else None,
            "client_user": {
                "id": campaign.client_user.id,
                "name": campaign.client_user.name,
                "email": campaign.client_user.email,
                "company": campaign.client_user.company,
                "business_number": getattr(campaign.client_user, 'business_number', None),
                "contact": campaign.client_user.contact,
                # 클라이언트 실제 회사 정보 추가
                "client_company_name": getattr(campaign.client_user, 'client_company_name', None),
                "client_business_number": getattr(campaign.client_user, 'client_business_number', None),
                "client_ceo_name": getattr(campaign.client_user, 'client_ceo_name', None),
                "client_company_address": getattr(campaign.client_user, 'client_company_address', None),
                "client_business_type": getattr(campaign.client_user, 'client_business_type', None),
                "client_business_item": getattr(campaign.client_user, 'client_business_item', None)
            } if campaign.client_user else None,
            "posts": [
                {
                    "id": post.id,
                    "title": post.title,
                    "work_type": post.work_type,
                    "workType": post.work_type,  # 프론트엔드 호환성
                    "topicStatus": post.topic_status,
                    "outline": post.outline,
                    "published_url": post.published_url,
                    "publishedUrl": post.published_url,  # 프론트엔드 호환성
                    "startDate": post.start_date,      # 기존 호환성
                    "dueDate": post.due_date,          # 기존 호환성
                    # "startDatetime": post.start_datetime.isoformat() if post.start_datetime else None,
                    # "dueDatetime": post.due_datetime.isoformat() if post.due_datetime else None,
                    "quantity": post.quantity,
                    "is_active": post.is_active
                } for post in (campaign.posts or []) if post.is_active
            ],
            # 캠페인 일정 정보 추가 (마이그레이션 후 활성화)
            # "invoiceDueDate": campaign.invoice_due_date.isoformat() if campaign.invoice_due_date else None,
            # "paymentDueDate": campaign.payment_due_date.isoformat() if campaign.payment_due_date else None,
            # "projectDueDate": campaign.project_due_date.isoformat() if campaign.project_due_date else None
        }
        serialized_campaigns.append(campaign_data)
    
    return {
        "data": serialized_campaigns,
        "pagination": {
            "page": current_page,
            "size": page_size,
            "total": total_count,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev,
            "offset": offset
        }
    }


@router.post("/", response_model=CampaignResponse)
async def create_campaign(
    request: Request,
    campaign_data: CampaignCreate,
    # JWT 인증된 사용자
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """새 캠페인 생성 (JWT 인증 기반 권한 확인)"""
    user_id = current_user.id
    user_role = current_user.role.value
    
    print(f"[CAMPAIGN-CREATE-JWT] Campaign creation request - User ID: {user_id}, Role: {user_role}")
    print(f"[CAMPAIGN-CREATE-JWT] Campaign data: {campaign_data}")
    
    # 권한 확인 - 관리자와 직원은 캠페인 생성 가능
    if user_role not in [UserRole.SUPER_ADMIN.value, UserRole.AGENCY_ADMIN.value, UserRole.STAFF.value]:
        print(f"[CAMPAIGN-CREATE-JWT] ERROR: Insufficient permissions - user_role={user_role}")
        raise HTTPException(status_code=403, detail="권한이 없습니다. 관리자와 직원만 캠페인을 생성할 수 있습니다.")
    
    # 새 캠페인 생성 - 안전한 기본값 처리
    try:
        current_time = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # 안전한 날짜 처리 함수
        def safe_datetime_parse(date_input):
            if date_input is None:
                return current_time
            # 이미 datetime 객체인 경우
            if isinstance(date_input, datetime):
                return date_input.replace(tzinfo=None)
            # string인 경우 파싱 시도
            if isinstance(date_input, str):
                try:
                    parsed = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
                    return parsed.replace(tzinfo=None)
                except ValueError:
                    print(f"[CAMPAIGN-CREATE-JWT] WARNING: Failed to parse date string: {date_input}")
                    return current_time
            return current_time
        
        # client_company에서 client_user_id 추출
        client_user_id = None
        client_company = campaign_data.client_company or "기본 클라이언트"
        
        # (ID: user_id) 패턴에서 user_id 추출
        if client_company and '(ID: ' in client_company and ')' in client_company:
            try:
                import re
                match = re.search(r'\(ID: (\d+)\)', client_company)
                if match:
                    client_user_id = int(match.group(1))
                    print(f"[CAMPAIGN-CREATE-JWT] Extracted client_user_id: {client_user_id}")
            except (ValueError, AttributeError) as e:
                print(f"[CAMPAIGN-CREATE-JWT] Failed to extract client_user_id: {e}")

        # 캠페인 생성 - client_user_id와 staff_id 처리
        campaign_kwargs = {
            "name": campaign_data.name.strip() if campaign_data.name else "새 캠페인",
            "description": campaign_data.description or '',
            "client_company": client_company,
            "budget": float(campaign_data.budget) if campaign_data.budget is not None else 1000000.0,
            "start_date": safe_datetime_parse(campaign_data.start_date),
            "end_date": safe_datetime_parse(campaign_data.end_date),
            "creator_id": user_id,
            "staff_id": campaign_data.staff_id if campaign_data.staff_id else user_id,  # 담당자 설정
            "status": CampaignStatus.ACTIVE
        }
        
        # client_user_id 필드가 존재하는지 확인 후 설정 (스키마 동기화 대응)
        try:
            # Campaign 모델에 client_user_id 속성이 있는지 확인
            if hasattr(Campaign, 'client_user_id'):
                campaign_kwargs["client_user_id"] = client_user_id
                print(f"[CAMPAIGN-CREATE-JWT] client_user_id field available, set to: {client_user_id}")
            else:
                print("[CAMPAIGN-CREATE-JWT] client_user_id field not available, skipping")
        except Exception as e:
            print(f"[CAMPAIGN-CREATE-JWT] Warning: Could not set client_user_id: {e}")

        new_campaign = Campaign(**campaign_kwargs)
        
        print(f"[CAMPAIGN-CREATE-JWT] SUCCESS: Creating campaign with data: name='{new_campaign.name}', budget={new_campaign.budget}")
        db.add(new_campaign)
        await db.commit()
        await db.refresh(new_campaign)
        print(f"[CAMPAIGN-CREATE-JWT] SUCCESS: Campaign created with ID {new_campaign.id}")
    except Exception as e:
        await db.rollback()
        print(f"[CAMPAIGN-CREATE-JWT] ERROR: Database operation failed: {e}")
        print(f"[CAMPAIGN-CREATE-JWT] ERROR: Exception type: {type(e).__name__}")
        print(f"[CAMPAIGN-CREATE-JWT] ERROR: Campaign data that failed: name='{campaign_data.name}', budget={campaign_data.budget}, client_company='{campaign_data.client_company}'")
        raise HTTPException(status_code=500, detail=f"캠페인 생성 중 오류가 발생했습니다: {str(e)}")
    
    # WebSocket 알림 전송 (일시적으로 비활성화)
    try:
        await manager.notify_campaign_update(
            campaign_id=new_campaign.id,
            update_type="생성",
            data={
                "name": new_campaign.name,
                "client_company": new_campaign.client_company,
                "budget": new_campaign.budget
            }
        )
    except Exception as e:
        # WebSocket 에러는 무시하고 계속 진행
        print(f"WebSocket notification failed: {e}")
    
    return new_campaign


@router.get("/staff-list", response_model=List[dict])
async def get_staff_members(
    request: Request,
    # JWT 인증된 사용자
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """같은 회사 직원 목록 조회 (JWT 인증 기반 대행사 어드민용)"""
    user_id = current_user.id
    user_role = current_user.role.value
    
    print(f"[STAFF-MEMBERS-JWT] Request from user_id={user_id}, user_role={user_role}")
    
    # 대행사 어드민과 슈퍼 어드민만 직원 목록 조회 가능
    if user_role not in [UserRole.AGENCY_ADMIN.value, UserRole.SUPER_ADMIN.value]:
        print(f"[STAFF-MEMBERS-JWT] ERROR: Insufficient permissions - user_role={user_role}")
        raise HTTPException(status_code=403, detail="직원 목록 조회 권한이 없습니다. 대행사 어드민 또는 슈퍼 어드민만 접근 가능합니다.")
    
    try:
        print(f"[STAFF-MEMBERS-JWT] Found user: {current_user.name}, company={current_user.company}")
        
        # 직원들 조회 (권한별 필터링)
        if user_role == UserRole.SUPER_ADMIN.value:
            # 슈퍼 어드민은 모든 직원과 대행사 어드민 조회 가능
            staff_query = select(User).where(
                User.role.in_([UserRole.STAFF, UserRole.AGENCY_ADMIN]),
                User.is_active == True
            )
        else:
            # 대행사 어드민은 같은 회사의 직원들만 조회
            staff_query = select(User).where(
                User.company == current_user.company,
                User.role == UserRole.STAFF,
                User.is_active == True
            )
        result = await db.execute(staff_query)
        staff_members = result.scalars().all()
        
        print(f"[STAFF-MEMBERS-JWT] Found {len(staff_members)} staff members")
        
        # 직원 정보를 딕셔너리로 변환
        staff_list = [
            {
                "id": staff.id,
                "name": staff.name,
                "email": staff.email,
                "company": staff.company
            }
            for staff in staff_members
        ]
        
        return staff_list
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[STAFF-MEMBERS-JWT] Unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"직원 목록 조회 중 오류: {str(e)}")


@router.get("/client-list", response_model=List[dict])
async def get_client_members(
    request: Request,
    campaign_id: Optional[int] = Query(None, description="Campaign ID to get related clients"),
    # JWT 인증된 사용자
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    캠페인의 클라이언트와 같은 회사의 클라이언트 목록을 반환
    campaign_id가 있으면 해당 캠페인의 client_user_id와 같은 회사의 클라이언트들
    campaign_id가 없으면 현재 사용자와 같은 회사의 클라이언트들
    """
    user_id = current_user.id
    user_role = current_user.role.value
    
    print(f"[CLIENT-MEMBERS-JWT] Request from user_id={user_id}, user_role={user_role}")
    print(f"[CLIENT-MEMBERS-JWT] Campaign ID: {campaign_id}")
    
    try:
        print(f"[CLIENT-MEMBERS-JWT] Found user: {current_user.name}, company={current_user.company}")
        
        target_company = None
        
        if campaign_id:
            # 캠페인 정보 조회
            campaign_query = select(Campaign).where(Campaign.id == campaign_id)
            campaign_result = await db.execute(campaign_query)
            campaign = campaign_result.scalar_one_or_none()
            
            if not campaign:
                raise HTTPException(status_code=404, detail="Campaign not found")
            
            print(f"[CLIENT-MEMBERS-JWT] Campaign found: {campaign.name}, client_user_id: {campaign.client_user_id}")
            
            if campaign.client_user_id:
                # 캠페인의 클라이언트 사용자 조회
                client_user_query = select(User).where(User.id == campaign.client_user_id)
                client_user_result = await db.execute(client_user_query)
                client_user = client_user_result.scalar_one_or_none()
                
                if client_user:
                    target_company = client_user.company
                    print(f"[CLIENT-MEMBERS-JWT] Using campaign client's company: {target_company}")
                else:
                    print(f"[CLIENT-MEMBERS-JWT] Campaign client user not found, using current user's company")
                    target_company = current_user.company
            else:
                print(f"[CLIENT-MEMBERS-JWT] Campaign has no client_user_id, using current user's company")
                target_company = current_user.company
        else:
            target_company = current_user.company
            print(f"[CLIENT-MEMBERS-JWT] No campaign_id provided, using current user's company: {target_company}")
        
        # 대상 회사의 클라이언트들 조회 (클라이언트 역할만)
        client_query = select(User).where(
            User.company == target_company,
            User.role == UserRole.CLIENT,
            User.is_active == True
        )
        result = await db.execute(client_query)
        client_members = result.scalars().all()
        
        print(f"[CLIENT-MEMBERS-JWT] Found {len(client_members)} client members in company: {target_company}")
        
        # 클라이언트 정보를 딕셔너리로 변환
        client_list = [
            {
                "id": client.id,
                "name": client.name,
                "email": client.email,
                "company": client.company
            }
            for client in client_members
        ]
        
        return client_list
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CLIENT-MEMBERS-JWT] Unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"클라이언트 목록 조회 중 오류: {str(e)}")


# OrderRequest 관련 엔드포인트들 - /{campaign_id} 라우트보다 먼저 정의
@router.get("/order-requests-test")
async def test_order_requests_endpoint(
    current_user: User = Depends(get_current_active_user)
):
    """OrderRequest 엔드포인트 테스트 - DB 접근 없이"""
    return {
        "status": "ok",
        "user_id": current_user.id,
        "user_role": current_user.role.value,
        "message": "엔드포인트 접근 성공"
    }

@router.get("/order-requests-health")
async def check_order_requests_table(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """OrderRequest 테이블 존재 여부 확인"""
    try:
        # 테이블 존재 확인을 위한 간단한 쿼리
        from sqlalchemy import text
        result = await db.execute(text("SELECT COUNT(*) FROM order_requests LIMIT 1"))
        count = result.scalar()
        return {"status": "ok", "table_exists": True, "count": count}
    except Exception as e:
        print(f"[ORDER-REQUEST-HEALTH] Table check failed: {e}")
        return {"status": "error", "table_exists": False, "error": str(e)}

@router.get("/order-requests")
async def get_all_order_requests(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """JWT 기반 전체 발주요청 목록 조회"""

    user_role = current_user.role.value
    user_company = current_user.company

    print(f"[ORDER-REQUESTS-LIST] Getting order requests for user_id={current_user.id}, role={user_role}, company={user_company}")

    try:
        # 발주요청 조회 (회사별 필터링 적용)
        from app.models.product import Product

        # User alias 생성 (테이블 충돌 방지)
        from sqlalchemy.orm import aliased
        RequesterUser = aliased(User)

        base_query = select(
            OrderRequest,
            Post,
            Campaign,
            Product,
            RequesterUser.name.label('requester_name')
        ).select_from(
            OrderRequest
        ).join(
            Post, OrderRequest.post_id == Post.id
        ).join(
            Campaign, OrderRequest.campaign_id == Campaign.id
        ).outerjoin(
            Product, Post.product_id == Product.id
        ).join(
            RequesterUser, OrderRequest.user_id == RequesterUser.id
        ).where(
            OrderRequest.is_active == True
        )

        # 권한별 필터링
        if user_role == UserRole.SUPER_ADMIN:
            # 슈퍼 어드민은 모든 발주요청 조회 가능
            print("[ORDER-REQUESTS-LIST] Super admin: showing all order requests")
            query = base_query
        else:
            # 일반 어드민은 본인 회사의 발주요청만 조회 가능
            print(f"[ORDER-REQUESTS-LIST] Company admin: filtering by company '{user_company}'")
            query = base_query.where(RequesterUser.company == user_company)

        query = query.order_by(OrderRequest.created_at.desc())

        result = await db.execute(query)
        order_requests_with_details = result.all()

        print(f"[ORDER-REQUESTS-LIST] Found {len(order_requests_with_details)} order requests")

        # 응답 데이터 구성
        order_requests_data = []
        for order_request, post, campaign, product, requester_name in order_requests_with_details:
            print(f"[ORDER-REQUEST-DATA] ID: {order_request.id}, post_id: {post.id}, product_id: {post.product_id}")
            print(f"[ORDER-REQUEST-DATA] Product: {product.name if product else 'None'}, cost: {product.cost if product else 'None'}, quantity: {post.quantity}")
            order_requests_data.append({
                "id": order_request.id,
                "title": order_request.title,
                "description": order_request.description,
                "status": order_request.status,
                "cost_price": order_request.cost_price,
                "resource_type": order_request.resource_type,
                "post_id": order_request.post_id,
                "user_id": order_request.user_id,
                "campaign_id": order_request.campaign_id,
                "created_at": order_request.created_at.isoformat(),
                "updated_at": order_request.updated_at.isoformat(),
                # 추가 정보
                "post_title": post.title,
                "campaign_name": campaign.name,
                "product_name": product.name if product else None,
                "product_cost": product.cost if product else 0,  # 제품 원가
                "quantity": post.quantity or 1,  # 수량
                "total_cost": (product.cost or 0) * (post.quantity or 1),  # 총 원가 (원가 * 수량)
                "requester_name": requester_name,
                "work_type": post.work_type
            })

        return order_requests_data

    except Exception as e:
        print(f"[ORDER-REQUESTS-LIST] Error getting order requests: {e}")
        print(f"[ORDER-REQUESTS-LIST] Error type: {type(e).__name__}")
        print(f"[ORDER-REQUESTS-LIST] Error args: {e.args}")
        import traceback
        print(f"[ORDER-REQUESTS-LIST] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"발주요청 목록 조회 중 오류가 발생했습니다: {str(e)}")

@router.put("/order-requests/{order_request_id}/status")
async def update_order_request_status(
    order_request_id: int,
    status_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """발주요청 상태 업데이트 (승인/거절)"""

    print(f"[ORDER-REQUEST-UPDATE] Updating order_request_id={order_request_id}, user_id={current_user.id}, user_role={current_user.role.value}")
    print(f"[ORDER-REQUEST-UPDATE] Status data: {status_data}")

    try:
        # 발주요청 조회
        query = select(OrderRequest).where(OrderRequest.id == order_request_id)
        result = await db.execute(query)
        order_request = result.scalar_one_or_none()

        if not order_request:
            raise HTTPException(status_code=404, detail="발주요청을 찾을 수 없습니다.")

        # 권한 확인 (회사별 어드민 권한 체크)
        user_role = current_user.role.value
        user_company = current_user.company

        print(f"[ORDER-REQUEST-UPDATE] User info - Role: '{user_role}', Company: '{user_company}'")

        # 슈퍼 어드민은 모든 발주요청 관리 가능
        if user_role == UserRole.SUPER_ADMIN:
            print(f"[ORDER-REQUEST-UPDATE] Super admin access granted")
        else:
            # 일반 어드민은 본인 회사의 발주요청만 관리 가능
            if user_role != UserRole.AGENCY_ADMIN:
                raise HTTPException(
                    status_code=403,
                    detail=f"발주요청 상태 변경 권한이 없습니다. 현재 역할: {user_role}"
                )

            # 발주요청을 생성한 사용자의 회사와 현재 사용자의 회사가 같은지 확인
            requester_query = select(User).where(User.id == order_request.user_id)
            requester_result = await db.execute(requester_query)
            requester = requester_result.scalar_one_or_none()

            if not requester:
                raise HTTPException(status_code=404, detail="발주요청 생성자를 찾을 수 없습니다.")

            requester_company = requester.company
            print(f"[ORDER-REQUEST-UPDATE] Company check - User: '{user_company}', Requester: '{requester_company}'")

            if user_company != requester_company:
                raise HTTPException(
                    status_code=403,
                    detail=f"다른 회사의 발주요청은 관리할 수 없습니다. (요청자 회사: {requester_company}, 현재 사용자 회사: {user_company})"
                )

        # 상태 업데이트
        new_status = status_data.get("status")
        comment = status_data.get("comment", "")

        if new_status not in ["대기", "승인", "거부", "완료"]:
            raise HTTPException(status_code=400, detail="유효하지 않은 상태입니다.")

        order_request.status = new_status

        # 승인/거부 시 Post 상태도 업데이트
        if order_request.post_id:
            post_query = select(Post).where(Post.id == order_request.post_id)
            post_result = await db.execute(post_query)
            post = post_result.scalar_one_or_none()

            if post:
                if new_status == "승인":
                    post.order_request_status = "발주 승인"
                elif new_status == "거부":
                    post.order_request_status = "발주 거절"

        await db.commit()
        await db.refresh(order_request)

        print(f"[ORDER-REQUEST-UPDATE] Successfully updated order request {order_request_id} to status: {new_status}")

        return {
            "message": f"발주요청이 {new_status}되었습니다.",
            "order_request": {
                "id": order_request.id,
                "title": order_request.title,
                "status": order_request.status,
                "cost_price": order_request.cost_price
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ORDER-REQUEST-UPDATE] Error updating order request: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"발주요청 상태 업데이트 중 오류가 발생했습니다: {str(e)}")


# 정적 경로들 - 동적 경로 {campaign_id} 보다 먼저 정의해야 함
@router.get("/migrate-db-now")
async def migrate_database_now():
    """데이터베이스 마이그레이션 즉시 실행 (임시 무인증 엔드포인트)"""
    try:
        from sqlalchemy import text
        from alembic import command
        from alembic.config import Config
        from app.db.database import engine

        # 현재 상태 확인
        async with engine.begin() as conn:
            try:
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                current_version = result.scalar()
            except:
                current_version = "none"

        # 마이그레이션 실행
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

        # 결과 확인
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            new_version = result.scalar()

            # 새 컬럼 확인
            check_result = await conn.execute(text("""
                SELECT column_name, table_name
                FROM information_schema.columns
                WHERE table_name IN ('posts', 'campaigns')
                AND column_name IN ('start_datetime', 'due_datetime', 'invoice_due_date', 'payment_due_date', 'project_due_date')
            """))
            columns = [f"{row[1]}.{row[0]}" for row in check_result.fetchall()]

        return {
            "success": True,
            "message": "마이그레이션 완료!",
            "old_version": current_version,
            "new_version": new_version,
            "new_columns": columns
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "마이그레이션 실패"
        }

@router.get("/test-auth")
async def test_auth(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """인증 테스트 엔드포인트"""
    print(f"[TEST-AUTH] 사용자 정보: {current_user.id}, {current_user.role}, {current_user.company}")
    return {
        "user_id": current_user.id,
        "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role),
        "company": current_user.company,
        "message": "인증 성공"
    }


@router.get("/approved-posts-expense")
async def get_approved_posts_expense(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """발주 승인된 posts의 원가*수량 총 지출 계산"""
    print(f"[APPROVED-POSTS-EXPENSE] ===== API 호출 시작 =====")

    try:
        # 사용자 정보 검증
        if not current_user:
            print(f"[APPROVED-POSTS-EXPENSE] ERROR: current_user is None")
            raise HTTPException(status_code=401, detail="인증되지 않은 사용자입니다")

        print(f"[APPROVED-POSTS-EXPENSE] 사용자 검증 완료: {current_user.id}")

        # 회사별 권한 확인
        user_role = current_user.role
        user_company = current_user.company

        print(f"[APPROVED-POSTS-EXPENSE] User: {current_user.id}")
        print(f"[APPROVED-POSTS-EXPENSE] Role: {user_role} (type: {type(user_role)})")
        print(f"[APPROVED-POSTS-EXPENSE] Role.value: {user_role.value if hasattr(user_role, 'value') else 'No value attr'}")
        print(f"[APPROVED-POSTS-EXPENSE] Company: {user_company}")

        # 먼저 간단한 승인된 OrderRequest 조회
        simple_query = select(OrderRequest).where(
            OrderRequest.status == "승인",
            OrderRequest.is_active == True
        )

        if user_role != UserRole.SUPER_ADMIN:
            print(f"[APPROVED-POSTS-EXPENSE] Adding company filter for {user_company}")
            from sqlalchemy.orm import aliased
            UserAlias = aliased(User)
            simple_query = simple_query.join(
                UserAlias, OrderRequest.user_id == UserAlias.id
            ).where(UserAlias.company == user_company)

        print(f"[APPROVED-POSTS-EXPENSE] Executing simple query...")
        result = await db.execute(simple_query)
        approved_orders = result.scalars().all()

        print(f"[APPROVED-POSTS-EXPENSE] Found {len(approved_orders)} approved orders")

        # 임시로 간단한 응답 반환
        return {
            "total_expense": 0,
            "count": len(approved_orders),
            "details": [],
            "message": f"Found {len(approved_orders)} approved orders - calculation in progress"
        }

    except HTTPException as he:
        print(f"[APPROVED-POSTS-EXPENSE] HTTPException: {he.status_code} - {he.detail}")
        raise he
    except Exception as e:
        import traceback
        print(f"[APPROVED-POSTS-EXPENSE] Unexpected Error: {e}")
        print(f"[APPROVED-POSTS-EXPENSE] Error type: {type(e).__name__}")
        print(f"[APPROVED-POSTS-EXPENSE] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"발주 승인 지출 계산 중 오류가 발생했습니다: {str(e)}")


@router.get("/order-status-list")
async def get_order_status_list(
    current_user: User = Depends(get_current_active_user),
):
    """발주요청 상태 목록 조회 (단순 버전)"""
    try:
        print(f"[ORDER-STATUS-LIST] Simple version for user: {current_user.id}")

        # DB 쿼리 없이 단순 반환
        status_list = [
            {"value": "대기", "label": "대기", "color": "yellow"},
            {"value": "승인", "label": "승인", "color": "green"},
            {"value": "거부", "label": "거부", "color": "red"}
        ]

        print(f"[ORDER-STATUS-LIST] Returning: {status_list}")

        return {
            "status_list": status_list,
            "success": True
        }

    except Exception as e:
        print(f"[ORDER-STATUS-LIST] Exception: {e}")
        return {
            "status_list": [],
            "success": False,
            "error": str(e)
        }


@router.get("/order-requesters")
async def get_order_requesters(
    current_user: User = Depends(get_current_active_user),
):
    """발주요청자 목록 조회 (단순 버전)"""
    try:
        print(f"[ORDER-REQUESTERS] Simple version for user: {current_user.id}")

        # DB 쿼리 없이 빈 목록 반환 (프론트엔드 fallback 활용)
        return {
            "requester_list": [],
            "success": True
        }

    except Exception as e:
        print(f"[ORDER-REQUESTERS] Exception: {e}")
        return {
            "requester_list": [],
            "success": False,
            "error": str(e)
        }


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign_detail(
    request: Request,
    campaign_id: int,
    # JWT 인증된 사용자
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """캠페인 상세 조회 (JWT 인증 기반 권한별 필터링)"""
    user_id = current_user.id
    user_role = current_user.role.value
    
    print(f"[CAMPAIGN-DETAIL-JWT] Request for campaign_id={campaign_id}, user_id={user_id}, user_role={user_role}")
    
    try:
        # 캠페인 찾기 (creator, client_user 관계 포함)
        query = select(Campaign).options(joinedload(Campaign.creator), joinedload(Campaign.client_user)).where(Campaign.id == campaign_id)
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            print(f"[CAMPAIGN-DETAIL-JWT] Campaign {campaign_id} not found")
            raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다")
        
        print(f"[CAMPAIGN-DETAIL-JWT] Found campaign: {campaign.name}")
        print(f"[CAMPAIGN-DETAIL-JWT] Campaign client_user_id: {campaign.client_user_id}")
        print(f"[CAMPAIGN-DETAIL-JWT] Campaign client_user: {campaign.client_user}")
        if campaign.client_user:
            print(f"[CAMPAIGN-DETAIL-JWT] Client user details: id={campaign.client_user.id}, name={campaign.client_user.name}")
            print(f"[CAMPAIGN-DETAIL-JWT] Client company info:")
            print(f"  - client_company_name: {getattr(campaign.client_user, 'client_company_name', None)}")
            print(f"  - client_business_number: {getattr(campaign.client_user, 'client_business_number', None)}")
            print(f"  - client_ceo_name: {getattr(campaign.client_user, 'client_ceo_name', None)}")
            print(f"  - client_company_address: {getattr(campaign.client_user, 'client_company_address', None)}")
            print(f"  - client_business_type: {getattr(campaign.client_user, 'client_business_type', None)}")
            print(f"  - client_business_item: {getattr(campaign.client_user, 'client_business_item', None)}")
        else:
            print(f"[CAMPAIGN-DETAIL-JWT] WARNING: client_user is None!")

        # JWT 기반 권한 확인
        if user_role == UserRole.SUPER_ADMIN.value:
            # 슈퍼 어드민은 모든 캠페인 접근 가능
            pass
        elif user_role == UserRole.CLIENT.value:
            # 클라이언트는 자신을 대상으로 한 캠페인만 조회 가능 (client_user_id 외래키 관계 사용)
            if campaign.client_user_id != user_id:
                print(f"[CAMPAIGN-DETAIL-JWT] CLIENT permission denied: client_user_id={campaign.client_user_id}, user_id={user_id}")
                raise HTTPException(status_code=403, detail="이 캠페인에 접근할 권한이 없습니다.")
        elif user_role == UserRole.AGENCY_ADMIN.value:
            # 대행사 어드민은 같은 회사 캠페인만 조회 가능
            if campaign.creator and campaign.creator.company != current_user.company:
                print(f"[CAMPAIGN-DETAIL-JWT] AGENCY_ADMIN permission denied: creator.company={campaign.creator.company}, user.company={current_user.company}")
                raise HTTPException(status_code=403, detail="이 캠페인에 접근할 권한이 없습니다.")
        elif user_role == UserRole.STAFF.value:
            # 직원은 자신이 생성한 캠페인만 조회 가능
            if campaign.creator_id != user_id:
                print(f"[CAMPAIGN-DETAIL-JWT] STAFF permission denied: campaign.creator_id={campaign.creator_id}, user_id={user_id}")
                raise HTTPException(status_code=403, detail="자신이 생성한 캠페인만 접근할 수 있습니다.")
        
        print(f"[CAMPAIGN-DETAIL-JWT] SUCCESS: Returning campaign {campaign.id} to user {user_id}")
        # 직렬화된 응답 반환 (executionStatus 매핑 포함)
        response_data = {
            "id": campaign.id,
            "name": campaign.name,
            "description": campaign.description,
            "status": campaign.status.value if campaign.status else None,
            "client_company": campaign.client_company,
            "budget": campaign.budget,
            "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
            "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
            "invoiceIssued": getattr(campaign, 'invoice_issued', False) if hasattr(campaign, 'invoice_issued') else False,  # 계산서 발행 완료
            "paymentCompleted": getattr(campaign, 'payment_completed', False) if hasattr(campaign, 'payment_completed') else False,  # 입금 완료
            "creator_id": campaign.creator_id,
            "staff_id": campaign.staff_id,  # 캠페인 담당 직원 ID 추가
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
            "creator_name": campaign.creator.name if campaign.creator else None,
            "client_name": campaign.client_company,
            "client_user": {
                "id": campaign.client_user.id,
                "name": campaign.client_user.name,
                "email": campaign.client_user.email,
                "company": campaign.client_user.company,
                "business_number": getattr(campaign.client_user, 'business_number', None),
                "contact": campaign.client_user.contact,
                # 클라이언트 실제 회사 정보 추가
                "client_company_name": getattr(campaign.client_user, 'client_company_name', None),
                "client_business_number": getattr(campaign.client_user, 'client_business_number', None),
                "client_ceo_name": getattr(campaign.client_user, 'client_ceo_name', None),
                "client_company_address": getattr(campaign.client_user, 'client_company_address', None),
                "client_business_type": getattr(campaign.client_user, 'client_business_type', None),
                "client_business_item": getattr(campaign.client_user, 'client_business_item', None)
            } if campaign.client_user else None
        }
        return response_data
        
    except HTTPException:
        raise  # HTTPException은 그대로 전달
    except Exception as e:
        print(f"[CAMPAIGN-DETAIL-JWT] Unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"캠페인 조회 중 오류: {str(e)}")


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    campaign_data: CampaignUpdate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    # JWT 인증된 사용자
    jwt_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """캠페인 수정"""
    print(f"[CAMPAIGN-UPDATE] Update request for campaign_id={campaign_id}, viewerId={viewerId}, viewerRole={viewerRole}")
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        try:
            # Node.js API 호환 모드
            user_id = viewerId or adminId
            user_role = viewerRole or adminRole
            
            if not user_id or not user_role:
                print(f"[CAMPAIGN-UPDATE] ERROR: Missing params - user_id={user_id}, user_role={user_role}")
                raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
            
            # URL 디코딩
            user_role = unquote(user_role).strip()
            print(f"[CAMPAIGN-UPDATE] Processing with user_id={user_id}, user_role='{user_role}'")
            
            # 캠페인 찾기 (creator 관계 포함)
            print(f"[CAMPAIGN-UPDATE] Searching for campaign with ID: {campaign_id}")
            campaign_query = select(Campaign).options(joinedload(Campaign.creator)).where(Campaign.id == campaign_id)
            result = await db.execute(campaign_query)
            campaign = result.unique().scalar_one_or_none()
            
            if not campaign:
                print(f"[CAMPAIGN-UPDATE] Campaign not found: {campaign_id}")
                raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다.")
            
            print(f"[CAMPAIGN-UPDATE] Found campaign: {campaign.name}, creator_id={campaign.creator_id}")
            
            # 권한 확인
            print(f"[CAMPAIGN-UPDATE] Checking user permissions for user_id: {user_id}")
            viewer_query = select(User).where(User.id == user_id)
            viewer_result = await db.execute(viewer_query)
            viewer = viewer_result.scalar_one_or_none()
            
            if not viewer:
                print(f"[CAMPAIGN-UPDATE] User not found: {user_id}")
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
            
            print(f"[CAMPAIGN-UPDATE] Found user: {viewer.name}, role={user_role}, company={viewer.company}")
            
            if user_role == UserRole.SUPER_ADMIN.value:
                # 슈퍼 어드민은 모든 캠페인 수정 가능
                print(f"[CAMPAIGN-UPDATE] Super admin can edit any campaign")
                pass
            elif user_role == UserRole.CLIENT.value:
                # 클라이언트는 다음 캠페인을 수정 가능:
                # 1) 본인이 생성한 캠페인 (creator_id == user_id)
                # 2) 본인을 위해 생성된 캠페인 (client_user_id == user_id)
                can_edit = False
                
                if campaign.creator_id == user_id:
                    can_edit = True
                    print(f"[CAMPAIGN-UPDATE] CLIENT can edit: own created campaign")
                elif campaign.client_user_id == user_id:
                    can_edit = True
                    print(f"[CAMPAIGN-UPDATE] CLIENT can edit: campaign created for them")
                
                if not can_edit:
                    raise HTTPException(status_code=403, detail="이 캠페인을 수정할 권한이 없습니다.")
            elif user_role == UserRole.AGENCY_ADMIN.value or ('agency' in user_role.lower() and 'admin' in user_role.lower()):
                # 대행사 어드민은 다음 캠페인을 수정 가능:
                # 1) 같은 회사 직원이 생성한 캠페인
                # 2) 클라이언트를 위해 생성된 캠페인 (client_user_id 기반)
                can_edit = False
                
                # 1) 캠페인 생성자가 같은 회사인지 확인
                creator_query = select(User).where(User.id == campaign.creator_id)
                creator_result = await db.execute(creator_query)
                creator = creator_result.scalar_one_or_none()
                
                if creator and creator.company == viewer.company:
                    can_edit = True
                    print(f"[CAMPAIGN-UPDATE] AGENCY_ADMIN can edit: same company creator")
                
                # 2) 클라이언트 사용자가 있고, 그 클라이언트의 캠페인을 대행사에서 관리하는지 확인
                if not can_edit and campaign.client_user_id:
                    client_query = select(User).where(User.id == campaign.client_user_id)
                    client_result = await db.execute(client_query)
                    client_user = client_result.scalar_one_or_none()
                    
                    # client_company 필드와 대행사가 관리하는 클라이언트인지 확인 (추가 로직 필요)
                    # 현재는 단순히 client_user_id가 있으면 편집 가능하게 설정
                    if client_user:
                        can_edit = True
                        print(f"[CAMPAIGN-UPDATE] AGENCY_ADMIN can edit: client campaign for user_id={campaign.client_user_id}")
                
                if not can_edit:
                    raise HTTPException(status_code=403, detail="이 캠페인을 수정할 권한이 없습니다.")
            elif user_role == UserRole.STAFF.value:
                # 직원은 자신이 생성한 캠페인만 수정 가능
                if campaign.creator_id != user_id:
                    raise HTTPException(status_code=403, detail="자신이 생성한 캠페인만 수정할 수 있습니다.")
            
            # 캠페인 정보 업데이트
            update_data = campaign_data.model_dump(exclude_unset=True)
            print(f"[CAMPAIGN-UPDATE] Update data received: {update_data}")
            
            for field, value in update_data.items():
                if field == 'user_id':
                    # 사용되지 않는 필드 무시
                    continue
                elif field == 'budget':
                    # budget 필드 처리 - None이나 빈 값인 경우 기본값 설정
                    if value is None or value == '' or value == 0:
                        # 기존 값 유지하거나 최소 예산 설정
                        if campaign.budget is None:
                            setattr(campaign, field, 1000000.0)  # 기본 예산 100만원
                            print(f"[CAMPAIGN-UPDATE] Set default budget: 1000000.0")
                        else:
                            print(f"[CAMPAIGN-UPDATE] Keeping existing budget: {campaign.budget}")
                    else:
                        try:
                            budget_value = float(value)
                            setattr(campaign, field, budget_value)
                            print(f"[CAMPAIGN-UPDATE] Updated budget: {budget_value}")
                        except (ValueError, TypeError) as e:
                            print(f"[CAMPAIGN-UPDATE] Invalid budget value: {value}, keeping existing: {campaign.budget}")
                elif field == 'creator_id' and value:
                    # 담당 직원 변경 (대행사 어드민만 가능) - UserRole enum 값 사용
                    if user_role != UserRole.AGENCY_ADMIN.value and not ('agency' in user_role.lower() and 'admin' in user_role.lower()):
                        print(f"[CAMPAIGN-UPDATE] Permission denied: user_role={user_role} cannot change creator_id")
                        continue
                    
                    # 새로운 담당 직원이 같은 회사인지 확인
                    new_staff_query = select(User).where(User.id == value)
                    new_staff_result = await db.execute(new_staff_query)
                    new_staff = new_staff_result.scalar_one_or_none()
                    
                    if not new_staff:
                        print(f"[CAMPAIGN-UPDATE] New staff not found: {value}")
                        continue
                        
                    if new_staff.company != viewer.company:
                        print(f"[CAMPAIGN-UPDATE] New staff not in same company: {new_staff.company} != {viewer.company}")
                        continue
                        
                    setattr(campaign, field, value)
                    print(f"[CAMPAIGN-UPDATE] Changed creator_id from {campaign.creator_id} to {value} ({new_staff.name})")
                elif field == 'staff_id' and value:
                    # 캠페인 담당자 변경 (대행사 어드민만 가능)
                    if user_role != UserRole.AGENCY_ADMIN.value and not ('agency' in user_role.lower() and 'admin' in user_role.lower()):
                        print(f"[CAMPAIGN-UPDATE] Permission denied: user_role={user_role} cannot change staff_id")
                        continue

                    # 새로운 담당 직원이 같은 회사인지 확인
                    new_staff_query = select(User).where(User.id == value)
                    new_staff_result = await db.execute(new_staff_query)
                    new_staff = new_staff_result.scalar_one_or_none()

                    if not new_staff:
                        print(f"[CAMPAIGN-UPDATE] New staff not found: {value}")
                        continue

                    if new_staff.company != viewer.company:
                        print(f"[CAMPAIGN-UPDATE] New staff not in same company: {new_staff.company} != {viewer.company}")
                        continue

                    setattr(campaign, field, value)
                    print(f"[CAMPAIGN-UPDATE] Changed staff_id from {getattr(campaign, 'staff_id', 'None')} to {value} ({new_staff.name})")
                elif field in ['start_date', 'end_date']:
                    # 날짜 필드는 안전하게 파싱 - 빈 값도 허용
                    def safe_datetime_parse(date_input):
                        if date_input is None or date_input == '':
                            return None  # 빈 값은 None으로 처리
                        # 이미 datetime 객체인 경우
                        if isinstance(date_input, datetime):
                            return date_input.replace(tzinfo=None)
                        # string인 경우 파싱 시도
                        if isinstance(date_input, str):
                            try:
                                parsed = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
                                return parsed.replace(tzinfo=None)
                            except ValueError:
                                print(f"[CAMPAIGN-UPDATE] WARNING: Failed to parse date string: {date_input}")
                                return None
                        return None
                    
                    try:
                        parsed_date = safe_datetime_parse(value)
                        setattr(campaign, field, parsed_date)
                        print(f"[CAMPAIGN-UPDATE] Updated {field}: {value} -> {parsed_date}")
                    except Exception as e:
                        print(f"[CAMPAIGN-UPDATE] Date parsing error for {field}: {e}")
                        # 날짜 파싱 실패 시 None 설정
                        setattr(campaign, field, None)
                elif field == 'client_company' and value:
                    # client_company 업데이트 시 client_user_id도 함께 업데이트
                    setattr(campaign, field, value)
                    
                    # client_company에서 client_user_id 추출
                    client_user_id = None
                    if value and '(ID: ' in value and ')' in value:
                        try:
                            import re
                            match = re.search(r'\(ID: (\d+)\)', value)
                            if match:
                                client_user_id = int(match.group(1))
                                print(f"[CAMPAIGN-UPDATE] Updated client_company: {value}")
                                print(f"[CAMPAIGN-UPDATE] Extracted client_user_id: {client_user_id}")
                            else:
                                print(f"[CAMPAIGN-UPDATE] Updated client_company: {value}")
                                print(f"[CAMPAIGN-UPDATE] No ID pattern found, client_user_id will be None")
                        except (ValueError, AttributeError) as e:
                            print(f"[CAMPAIGN-UPDATE] Failed to extract client_user_id: {e}")
                    else:
                        # client_company가 None이거나 빈 문자열인 경우
                        print(f"[CAMPAIGN-UPDATE] Updated client_company: {value}")
                        print(f"[CAMPAIGN-UPDATE] Set client_user_id to None (no value or pattern)")
                    
                    # client_user_id 필드가 존재하는지 확인 후 설정 (스키마 동기화 대응)
                    try:
                        if hasattr(campaign, 'client_user_id'):
                            setattr(campaign, 'client_user_id', client_user_id)
                            print(f"[CAMPAIGN-UPDATE] client_user_id field available, updated to: {client_user_id}")
                        else:
                            print("[CAMPAIGN-UPDATE] client_user_id field not available, skipping")
                    except Exception as e:
                        print(f"[CAMPAIGN-UPDATE] Warning: Could not update client_user_id: {e}")
                elif field == 'staff_id' and value:
                    # 캠페인 담당자 변경 (대행사 어드민만 가능)
                    if user_role != UserRole.AGENCY_ADMIN.value and not ('agency' in user_role.lower() and 'admin' in user_role.lower()) and user_role != UserRole.SUPER_ADMIN.value:
                        print(f"[CAMPAIGN-UPDATE] Permission denied: user_role={user_role} cannot change staff_id")
                        continue

                    # 새로운 담당 직원이 같은 회사인지 확인
                    new_staff_query = select(User).where(User.id == value)
                    new_staff_result = await db.execute(new_staff_query)
                    new_staff = new_staff_result.scalar_one_or_none()

                    if not new_staff:
                        print(f"[CAMPAIGN-UPDATE] New staff not found: {value}")
                        continue

                    # 대행사 어드민의 경우 같은 회사 직원만 배정 가능
                    if user_role == UserRole.AGENCY_ADMIN.value and hasattr(viewer, 'company') and new_staff.company != viewer.company:
                        print(f"[CAMPAIGN-UPDATE] New staff not in same company: {new_staff.company} != {viewer.company}")
                        continue

                    setattr(campaign, field, value)
                    print(f"[CAMPAIGN-UPDATE] Changed staff_id from {getattr(campaign, 'staff_id', 'None')} to {value} ({new_staff.name})")
                elif field in ['invoice_issued', 'payment_completed']:
                    # 재무 상태 필드 처리
                    try:
                        bool_value = bool(value) if value is not None else False
                        setattr(campaign, field, bool_value)
                        print(f"[CAMPAIGN-UPDATE] Updated financial field {field}: {value} -> {bool_value}")
                    except Exception as e:
                        print(f"[CAMPAIGN-UPDATE] Warning: Could not update {field}: {e}")
                elif hasattr(campaign, field):
                    setattr(campaign, field, value)
                    print(f"[CAMPAIGN-UPDATE] Updated {field}: {value}")
                    # executionStatus 업데이트 특별 로깅
                    if field == 'executionStatus':
                        print(f"[CAMPAIGN-UPDATE] ExecutionStatus successfully updated to: {value}")
                        print(f"[CAMPAIGN-UPDATE] Campaign.executionStatus value: {getattr(campaign, 'executionStatus', 'NOT_FOUND')}")
        
            # 업데이트 시간과 업데이트한 사용자 정보 추가
            campaign.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(campaign)
            
            print(f"[CAMPAIGN-UPDATE] SUCCESS: Campaign {campaign_id} updated by user {user_id}")

            # 직렬화된 응답 반환 (executionStatus 매핑 포함)
            response_data = {
                "id": campaign.id,
                "name": campaign.name,
                "description": campaign.description,
                "status": campaign.status.value if campaign.status else None,
                "client_company": campaign.client_company,
                "budget": campaign.budget,
                "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
                "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
                "invoiceIssued": getattr(campaign, 'invoice_issued', False),  # 계산서 발행 완료
                "paymentCompleted": getattr(campaign, 'payment_completed', False),  # 입금 완료
                "creator_id": campaign.creator_id,
                "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
                "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
                "creator_name": campaign.creator.name if campaign.creator else None,
                "client_name": campaign.client_company
            }
            return response_data
            
        except HTTPException:
            raise  # HTTPException은 그대로 전달
        except Exception as e:
            print(f"[CAMPAIGN-UPDATE] Unexpected error: {type(e).__name__}: {e}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"캠페인 수정 중 오류: {str(e)}")
    else:
        # JWT 토큰 기반 API 모드
        print(f"[CAMPAIGN-UPDATE] JWT 토큰 기반 수정 요청: campaign_id={campaign_id}")
        
        # JWT 토큰에서 사용자 정보 추출
        user_id = jwt_user.id
        user_role = jwt_user.role
        
        print(f"[CAMPAIGN-UPDATE] JWT User: id={user_id}, role={user_role}")
        
        # 동일한 수정 로직 사용 (Query parameter 방식과 동일)
        try:
            # 캠페인 조회
            campaign_query = select(Campaign).options(joinedload(Campaign.creator)).where(Campaign.id == campaign_id)
            result = await db.execute(campaign_query)
            campaign = result.unique().scalar_one_or_none()
            
            if not campaign:
                print(f"[CAMPAIGN-UPDATE] Campaign not found: {campaign_id}")
                raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다.")
            
            print(f"[CAMPAIGN-UPDATE] Found campaign: {campaign.name}, creator_id={campaign.creator_id}")
            
            # 권한 확인 (Query parameter 방식과 동일한 로직)
            if user_role == UserRole.SUPER_ADMIN.value:
                print(f"[CAMPAIGN-UPDATE] Super admin can edit any campaign")
                pass
            elif user_role == UserRole.CLIENT.value:
                can_edit = False
                if campaign.creator_id == user_id:
                    can_edit = True
                    print(f"[CAMPAIGN-UPDATE] CLIENT can edit: own created campaign")
                elif campaign.client_user_id == user_id:
                    can_edit = True
                    print(f"[CAMPAIGN-UPDATE] CLIENT can edit: campaign created for them")
                
                if not can_edit:
                    raise HTTPException(status_code=403, detail="이 캠페인을 수정할 권한이 없습니다.")
            elif user_role == UserRole.AGENCY_ADMIN.value or ('agency' in user_role.lower() and 'admin' in user_role.lower()):
                can_edit = False
                creator_query = select(User).where(User.id == campaign.creator_id)
                creator_result = await db.execute(creator_query)
                creator = creator_result.scalar_one_or_none()
                
                if creator and creator.company == jwt_user.company:
                    can_edit = True
                    print(f"[CAMPAIGN-UPDATE] AGENCY_ADMIN can edit: same company campaign")
                elif campaign.client_user_id:
                    client_query = select(User).where(User.id == campaign.client_user_id)
                    client_result = await db.execute(client_query)
                    client = client_result.scalar_one_or_none()
                    if client and client.company == jwt_user.company:
                        can_edit = True
                        print(f"[CAMPAIGN-UPDATE] AGENCY_ADMIN can edit: client from same company")
                
                if not can_edit:
                    raise HTTPException(status_code=403, detail="이 캠페인을 수정할 권한이 없습니다.")
            else:
                raise HTTPException(status_code=403, detail="캠페인 수정 권한이 없습니다.")
            
            # 캠페인 데이터 업데이트 (Query parameter 방식과 동일한 로직)
            update_data = campaign_data.dict(exclude_unset=True)
            print(f"[CAMPAIGN-UPDATE] Update data: {update_data}")
            
            for field, value in update_data.items():
                if field == 'budget':
                    if value is None or value == '' or value == 0:
                        if campaign.budget is None:
                            setattr(campaign, field, 1000000.0)
                            print(f"[CAMPAIGN-UPDATE] Set default budget: 1000000.0")
                        else:
                            print(f"[CAMPAIGN-UPDATE] Keeping existing budget: {campaign.budget}")
                    else:
                        try:
                            budget_value = float(value)
                            setattr(campaign, field, budget_value)
                            print(f"[CAMPAIGN-UPDATE] Updated budget: {budget_value}")
                        except (ValueError, TypeError) as e:
                            print(f"[CAMPAIGN-UPDATE] Invalid budget value: {value}, keeping existing: {campaign.budget}")
                elif field in ['start_date', 'end_date']:
                    if value is None or value == '':
                        if getattr(campaign, field) is None:
                            default_date = datetime.now()
                            setattr(campaign, field, default_date)
                            print(f"[CAMPAIGN-UPDATE] Set default {field}: {default_date}")
                        else:
                            print(f"[CAMPAIGN-UPDATE] Keeping existing {field}: {getattr(campaign, field)}")
                    else:
                        try:
                            if isinstance(value, str):
                                parsed_date = datetime.fromisoformat(value.replace('Z', '+00:00'))
                            else:
                                parsed_date = value
                            setattr(campaign, field, parsed_date)
                            print(f"[CAMPAIGN-UPDATE] Updated {field}: {value} -> {parsed_date}")
                        except Exception as e:
                            print(f"[CAMPAIGN-UPDATE] Date parsing error for {field}: {e}, keeping existing value")
                            # 파싱 오류 시 기존 값을 유지 (NULL 값 설정하지 않음)
                            pass
                elif field == 'client_company' and value:
                    setattr(campaign, field, value)
                    client_user_id = None
                    if value and '(ID: ' in value and ')' in value:
                        try:
                            import re
                            match = re.search(r'\(ID: (\d+)\)', value)
                            if match:
                                client_user_id = int(match.group(1))
                                print(f"[CAMPAIGN-UPDATE] Updated client_company: {value}")
                                print(f"[CAMPAIGN-UPDATE] Extracted client_user_id: {client_user_id}")
                        except (ValueError, AttributeError) as e:
                            print(f"[CAMPAIGN-UPDATE] Failed to extract client_user_id: {e}")
                    
                    try:
                        if hasattr(campaign, 'client_user_id'):
                            setattr(campaign, 'client_user_id', client_user_id)
                            print(f"[CAMPAIGN-UPDATE] client_user_id field available, updated to: {client_user_id}")
                        else:
                            print("[CAMPAIGN-UPDATE] client_user_id field not available, skipping")
                    except Exception as e:
                        print(f"[CAMPAIGN-UPDATE] Warning: Could not update client_user_id: {e}")
                elif field == 'staff_id' and value:
                    # 캠페인 담당자 변경 (대행사 어드민만 가능)
                    if user_role != UserRole.AGENCY_ADMIN.value and not ('agency' in user_role.lower() and 'admin' in user_role.lower()) and user_role != UserRole.SUPER_ADMIN.value:
                        print(f"[CAMPAIGN-UPDATE] Permission denied: user_role={user_role} cannot change staff_id")
                        continue

                    # 새로운 담당 직원이 같은 회사인지 확인
                    new_staff_query = select(User).where(User.id == value)
                    new_staff_result = await db.execute(new_staff_query)
                    new_staff = new_staff_result.scalar_one_or_none()

                    if not new_staff:
                        print(f"[CAMPAIGN-UPDATE] New staff not found: {value}")
                        continue

                    # 대행사 어드민의 경우 같은 회사 직원만 배정 가능
                    if user_role == UserRole.AGENCY_ADMIN.value and hasattr(viewer, 'company') and new_staff.company != viewer.company:
                        print(f"[CAMPAIGN-UPDATE] New staff not in same company: {new_staff.company} != {viewer.company}")
                        continue

                    setattr(campaign, field, value)
                    print(f"[CAMPAIGN-UPDATE] Changed staff_id from {getattr(campaign, 'staff_id', 'None')} to {value} ({new_staff.name})")
                elif field in ['invoice_issued', 'payment_completed']:
                    # 재무 상태 필드 처리
                    try:
                        bool_value = bool(value) if value is not None else False
                        setattr(campaign, field, bool_value)
                        print(f"[CAMPAIGN-UPDATE] Updated financial field {field}: {value} -> {bool_value}")
                    except Exception as e:
                        print(f"[CAMPAIGN-UPDATE] Warning: Could not update {field}: {e}")
                elif hasattr(campaign, field):
                    setattr(campaign, field, value)
                    print(f"[CAMPAIGN-UPDATE] Updated {field}: {value}")
                    # executionStatus 업데이트 특별 로깅
                    if field == 'executionStatus':
                        print(f"[CAMPAIGN-UPDATE] ExecutionStatus successfully updated to: {value}")
                        print(f"[CAMPAIGN-UPDATE] Campaign.executionStatus value: {getattr(campaign, 'executionStatus', 'NOT_FOUND')}")
            
            # 업데이트 시간 설정
            campaign.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(campaign)
            
            print(f"[CAMPAIGN-UPDATE] SUCCESS: Campaign {campaign_id} updated by JWT user {user_id}")

            # 직렬화된 응답 반환 (executionStatus 매핑 포함)
            response_data = {
                "id": campaign.id,
                "name": campaign.name,
                "description": campaign.description,
                "status": campaign.status.value if campaign.status else None,
                "client_company": campaign.client_company,
                "budget": campaign.budget,
                "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
                "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
                "invoiceIssued": getattr(campaign, 'invoice_issued', False),  # 계산서 발행 완료
                "paymentCompleted": getattr(campaign, 'payment_completed', False),  # 입금 완료
                "creator_id": campaign.creator_id,
                "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
                "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
                "creator_name": campaign.creator.name if campaign.creator else None,
                "client_name": campaign.client_company
            }
            return response_data
            
        except HTTPException:
            raise  # HTTPException은 그대로 전달
        except Exception as e:
            print(f"[CAMPAIGN-UPDATE] Unexpected error in JWT mode: {type(e).__name__}: {e}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"캠페인 수정 중 오류: {str(e)}")


@router.get("/{campaign_id}/financial_summary/", response_model=dict)
async def get_campaign_financial_summary(
    campaign_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """캠페인 재무 요약 정보 조회"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 캠페인 찾기
        campaign_query = select(Campaign).where(Campaign.id == campaign_id)
        result = await db.execute(campaign_query)
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다.")
        
        # 권한 확인
        viewer_query = select(User).where(User.id == user_id)
        viewer_result = await db.execute(viewer_query)
        viewer = viewer_result.scalar_one_or_none()
        
        if not viewer:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 재무 요약 데이터 (캠페인 budget 기반 자동 계산)
        budget_amount = float(campaign.budget) if campaign.budget else 0.0
        total_cost = budget_amount * 0.45  # 지출 금액
        total_revenue = budget_amount  # 매출은 예산과 동일하게 설정
        total_profit = total_revenue - total_cost  # 순이익 계산
        
        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "total_budget": budget_amount,
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "total_profit": total_profit,
            "spent_amount": total_cost,
            "remaining_budget": budget_amount - total_cost,
            "total_tasks": 10,  # 전체 작업 수 (예시)
            "completed_tasks": 7,  # 완료된 작업 수 (예시)
            "expense_categories": {
                "광고비": budget_amount * 0.25,
                "제작비": budget_amount * 0.15,
                "기타": budget_amount * 0.05
            },
            "roi": 2.3,
            "conversion_rate": 0.045,
            "completion_rate": 0.7,  # 완료율
            "margin_rate": (total_profit / total_revenue) if total_revenue > 0 else 0  # 마진율
        }
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 재무 요약 조회 구현
        raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/{campaign_id}/posts/", response_model=list)
async def get_campaign_posts(
    campaign_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """캠페인 게시물 목록 조회"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 캠페인 존재 여부 확인
        campaign_query = select(Campaign).where(Campaign.id == campaign_id)
        result = await db.execute(campaign_query)
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다.")
        
        # 권한 확인 (financial_summary와 동일한 로직)
        viewer_query = select(User).where(User.id == user_id)
        viewer_result = await db.execute(viewer_query)
        viewer = viewer_result.scalar_one_or_none()
        
        if not viewer:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 캠페인의 모든 포스트 조회 (Product 조인)
        from app.models.product import Product
        posts_query = select(Post, Product).outerjoin(Product, Post.product_id == Product.id).where(
            Post.campaign_id == campaign_id,
            Post.is_active == True
        )
        posts_result = await db.execute(posts_query)
        posts_with_products = posts_result.all()

        # PostResponse 형태로 직렬화 (product name 포함)
        posts_data = []
        for post, product in posts_with_products:
            posts_data.append({
                "id": post.id,
                "title": post.title,
                "workType": post.work_type,
                "topicStatus": post.topic_status,
                "outline": post.outline,
                "outlineStatus": post.outline_status,
                "images": post.images or [],
                "publishedUrl": post.published_url,
                "orderRequestStatus": post.order_request_status,
                "orderRequestId": post.order_request_id,
                "startDate": post.start_date,
                "dueDate": post.due_date,
                "productId": post.product_id,
                "productName": product.name if product else None,  # 제품명 추가
                "productCost": product.cost if product else None,  # 제품 원가 추가
                "quantity": post.quantity,
                "campaignId": post.campaign_id,
                "createdAt": post.created_at.isoformat() if post.created_at else None
            })

        return posts_data
    else:
        # JWT 기반 API 호출은 별도 엔드포인트 사용 요구
        raise HTTPException(
            status_code=400,
            detail="JWT 기반 인증을 위해서는 /api/campaigns/{campaign_id}/posts/jwt 엔드포인트를 사용하세요"
        )


# JWT 기반 캠페인 포스트 조회 전용 엔드포인트
@router.get("/{campaign_id}/posts/jwt", response_model=list)
async def get_campaign_posts_jwt(
    campaign_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """JWT 인증 기반 캠페인 게시물 목록 조회"""

    print(f"[CAMPAIGN-POSTS-JWT] Request for campaign_id={campaign_id}, user_id={current_user.id}, user_role={current_user.role.value}")

    # 캠페인 존재 여부 확인
    campaign_query = select(Campaign).where(Campaign.id == campaign_id)
    result = await db.execute(campaign_query)
    campaign = result.scalar_one_or_none()

    if not campaign:
        print(f"[CAMPAIGN-POSTS-JWT] Campaign {campaign_id} not found")
        raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다")

    # 캠페인의 모든 포스트 조회 (Product 조인)
    from app.models.product import Product
    posts_query = select(Post, Product).outerjoin(Product, Post.product_id == Product.id).where(
        Post.campaign_id == campaign_id,
        Post.is_active == True
    )
    posts_result = await db.execute(posts_query)
    posts_with_products = posts_result.all()

    print(f"[CAMPAIGN-POSTS-JWT] Found {len(posts_with_products)} posts for campaign {campaign_id}")

    # PostResponse 형태로 직렬화 (product name 포함)
    posts_data = []
    for post, product in posts_with_products:
        posts_data.append({
            "id": post.id,
            "title": post.title,
            "workType": post.work_type,
            "topicStatus": post.topic_status,
            "outline": post.outline,
            "outlineStatus": post.outline_status,
            "images": post.images or [],
            "publishedUrl": post.published_url,
            "orderRequestStatus": post.order_request_status,
            "orderRequestId": post.order_request_id,
            "startDate": post.start_date,  # 기존 호환성
            "dueDate": post.due_date,      # 기존 호환성
            # "startDatetime": post.start_datetime.isoformat() if post.start_datetime else None,  # 새로운 DateTime
            # "dueDatetime": post.due_datetime.isoformat() if post.due_datetime else None,        # 새로운 DateTime
            "productId": post.product_id,
            "productName": product.name if product else None,  # 제품명 추가
            "quantity": post.quantity,
            "campaignId": post.campaign_id,
            "createdAt": post.created_at.isoformat() if post.created_at else None
        })

    return posts_data


@router.post("/{campaign_id}/posts/", response_model=PostResponse)
async def create_campaign_post(
    campaign_id: int,
    post_data: PostCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """캠페인에 새 업무(포스트) 생성 (JWT 기반)"""
    print(f"[CREATE-POST] JWT User: {current_user.name}, Campaign: {campaign_id}, Data: {post_data.dict()}")

    try:
        # 캠페인 존재 여부 및 권한 확인
        campaign_query = select(Campaign).where(Campaign.id == campaign_id)
        result = await db.execute(campaign_query)
        campaign = result.scalar_one_or_none()

        if not campaign:
            raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다")

        # 권한 확인: 캠페인 생성자이거나 관리자 권한 필요
        user_role = current_user.role.value
        if (campaign.creator_id != current_user.id and
            user_role not in [UserRole.SUPER_ADMIN.value, UserRole.AGENCY_ADMIN.value]):
            raise HTTPException(status_code=403, detail="이 캠페인에 업무를 생성할 권한이 없습니다")

        # 새 포스트 생성
        new_post = Post(
            title=post_data.title,
            work_type=post_data.work_type,
            topic_status=post_data.topic_status,
            outline=post_data.outline,
            outline_status=post_data.outline_status,
            images=post_data.images or [],
            published_url=post_data.published_url,
            order_request_status=post_data.order_request_status,
            order_request_id=post_data.order_request_id,
            start_date=post_data.start_date,
            due_date=post_data.due_date,
            product_id=post_data.product_id,
            quantity=post_data.quantity or 1,
            campaign_id=campaign_id
        )

        db.add(new_post)
        await db.commit()
        await db.refresh(new_post)

        # Product 정보도 함께 조회해서 반환
        product_name = None
        if new_post.product_id:
            from app.models.product import Product
            product_query = select(Product).where(Product.id == new_post.product_id)
            product_result = await db.execute(product_query)
            product = product_result.scalar_one_or_none()
            product_name = product.name if product else None

        print(f"[CREATE-POST] SUCCESS: Created post {new_post.id} for campaign {campaign_id}")

        # 수동으로 직렬화해서 productName 포함
        return {
            "id": new_post.id,
            "title": new_post.title,
            "work_type": new_post.work_type,
            "topic_status": new_post.topic_status,
            "outline": new_post.outline,
            "outline_status": new_post.outline_status,
            "images": new_post.images or [],
            "published_url": new_post.published_url,
            "order_request_status": new_post.order_request_status,
            "order_request_id": new_post.order_request_id,
            "start_date": new_post.start_date,
            "due_date": new_post.due_date,
            "product_id": new_post.product_id,
            "productName": product_name,  # 제품명 추가
            "quantity": new_post.quantity,
            "campaign_id": new_post.campaign_id,
            "created_at": new_post.created_at.isoformat() if new_post.created_at else None,
            "updated_at": new_post.updated_at.isoformat() if new_post.updated_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[CREATE-POST] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"업무 생성 중 오류: {str(e)}")


@router.put("/{campaign_id}/posts/{post_id}", response_model=dict)
async def update_campaign_post(
    campaign_id: int,
    post_id: int,
    post_data: dict,  # 유연한 업데이트를 위해 dict 사용
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """캠페인의 업무(포스트) 수정 (JWT 기반)"""
    print(f"[UPDATE-POST] JWT User: {current_user.name}, Campaign: {campaign_id}, Post: {post_id}, Data: {post_data}")

    try:
        # 캠페인 및 포스트 존재 여부 확인
        campaign_query = select(Campaign).where(Campaign.id == campaign_id)
        campaign_result = await db.execute(campaign_query)
        campaign = campaign_result.scalar_one_or_none()

        if not campaign:
            raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다")

        post_query = select(Post).where(Post.id == post_id, Post.campaign_id == campaign_id, Post.is_active == True)
        post_result = await db.execute(post_query)
        post = post_result.scalar_one_or_none()

        if not post:
            raise HTTPException(status_code=404, detail="업무를 찾을 수 없습니다")

        # 권한 확인: 캠페인 생성자이거나 관리자 권한 필요
        user_role = current_user.role.value
        if (campaign.creator_id != current_user.id and
            user_role not in [UserRole.SUPER_ADMIN.value, UserRole.AGENCY_ADMIN.value]):
            raise HTTPException(status_code=403, detail="이 업무를 수정할 권한이 없습니다")

        # 업데이트할 필드들 처리
        if 'title' in post_data:
            post.title = post_data['title']
        if 'workType' in post_data:
            post.work_type = post_data['workType']
        if 'topicStatus' in post_data:
            post.topic_status = post_data['topicStatus']
        if 'outline' in post_data:
            post.outline = post_data['outline']
        if 'outlineStatus' in post_data:
            post.outline_status = post_data['outlineStatus']
        if 'images' in post_data:
            post.images = post_data['images']
        if 'productId' in post_data:
            # productId를 정수로 변환
            try:
                post.product_id = int(post_data['productId']) if post_data['productId'] else None
                print(f"[UPDATE-POST] Updated product_id: {post.product_id}")
            except (ValueError, TypeError) as e:
                print(f"[UPDATE-POST] Invalid productId: {post_data['productId']}, error: {e}")
                raise HTTPException(status_code=400, detail=f"잘못된 상품 ID 형식: {post_data['productId']}")
        if 'quantity' in post_data:
            # quantity를 정수로 변환
            try:
                post.quantity = int(post_data['quantity']) if post_data['quantity'] else 1
                print(f"[UPDATE-POST] Updated quantity: {post.quantity}")
            except (ValueError, TypeError) as e:
                print(f"[UPDATE-POST] Invalid quantity: {post_data['quantity']}, error: {e}")
                raise HTTPException(status_code=400, detail=f"잘못된 수량 형식: {post_data['quantity']}")
        if 'startDate' in post_data:
            post.start_date = post_data['startDate']
        if 'dueDate' in post_data:
            post.due_date = post_data['dueDate']
        if 'published_url' in post_data:
            post.published_url = post_data['published_url']
            print(f"[UPDATE-POST] Updated published_url: {post_data['published_url']}")

        # 업무 수정 시 발주 요청 상태 초기화
        print(f"[UPDATE-POST] 업무 수정으로 인한 발주 요청 상태 초기화: Post {post.id}")
        print(f"[UPDATE-POST] 이전 발주 상태: orderRequestStatus={post.order_request_status}, orderRequestId={post.order_request_id}")

        post.order_request_status = None
        post.order_request_id = None

        print(f"[UPDATE-POST] 발주 요청 상태 초기화 완료")

        await db.commit()
        await db.refresh(post)

        # Product 정보도 함께 조회해서 반환
        product_name = None
        if post.product_id:
            from app.models.product import Product
            product_query = select(Product).where(Product.id == post.product_id)
            product_result = await db.execute(product_query)
            product = product_result.scalar_one_or_none()
            product_name = product.name if product else None

        print(f"[UPDATE-POST] SUCCESS: Updated post {post.id} for campaign {campaign_id}")

        # 수정된 포스트 반환
        return {
            "id": post.id,
            "title": post.title,
            "work_type": post.work_type,
            "topic_status": post.topic_status,
            "outline": post.outline,
            "outline_status": post.outline_status,
            "images": post.images or [],
            "published_url": post.published_url,
            "publishedUrl": post.published_url,  # 프론트엔드 호환성
            "order_request_status": post.order_request_status,
            "order_request_id": post.order_request_id,
            "start_date": post.start_date,
            "due_date": post.due_date,
            "product_id": post.product_id,
            "productName": product_name,
            "quantity": post.quantity,
            "campaign_id": post.campaign_id,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "updated_at": post.updated_at.isoformat() if post.updated_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[UPDATE-POST] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"업무 수정 중 오류: {str(e)}")


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    # JWT 기반 인증
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """캠페인 삭제 (권한별 제한)"""
    from datetime import datetime
    import uuid

    request_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    print(f"[CAMPAIGN-DELETE] 🟢 START Request {request_id} at {timestamp}")
    print(f"[CAMPAIGN-DELETE] Request for campaign_id={campaign_id}, viewerId={viewerId}, viewerRole={viewerRole}")
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        try:
            # Node.js API 호환 모드
            user_id = viewerId or adminId
            user_role = viewerRole or adminRole
            
            if not user_id or not user_role:
                print(f"[CAMPAIGN-DELETE] ERROR: Missing params - user_id={user_id}, user_role={user_role}")
                raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
            
            # URL 디코딩
            user_role = unquote(user_role).strip()
            print(f"[CAMPAIGN-DELETE] Processing with user_id={user_id}, user_role='{user_role}'")
            
            # 캠페인 찾기 (creator 관계 포함)
            campaign_query = select(Campaign).options(joinedload(Campaign.creator)).where(Campaign.id == campaign_id)
            result = await db.execute(campaign_query)
            campaign = result.unique().scalar_one_or_none()
            
            if not campaign:
                print(f"[CAMPAIGN-DELETE] Campaign not found: {campaign_id}")
                raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다.")
            
            print(f"[CAMPAIGN-DELETE] Found campaign: {campaign.name}, creator_id={campaign.creator_id}")
            
            # 사용자 권한 확인
            viewer_query = select(User).where(User.id == user_id)
            viewer_result = await db.execute(viewer_query)
            viewer = viewer_result.scalar_one_or_none()
            
            if not viewer:
                print(f"[CAMPAIGN-DELETE] User not found: {user_id}")
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
            
            print(f"[CAMPAIGN-DELETE] Viewer info: {viewer.name}, role={user_role}, company={viewer.company}")
            
            # 권한 검사 (UserRole enum 값 사용)
            can_delete = False
            
            if user_role == UserRole.SUPER_ADMIN.value or 'super' in user_role.lower():
                # 슈퍼 어드민은 모든 캠페인 삭제 가능
                can_delete = True
                print(f"[CAMPAIGN-DELETE] Super admin can delete any campaign")
            elif user_role == UserRole.AGENCY_ADMIN.value or ('agency' in user_role.lower() and 'admin' in user_role.lower()):
                # 대행사 어드민은 같은 회사의 모든 캠페인 삭제 가능
                if campaign.creator and campaign.creator.company == viewer.company:
                    can_delete = True
                    print(f"[CAMPAIGN-DELETE] Agency admin can delete campaign from same company")
                else:
                    print(f"[CAMPAIGN-DELETE] Agency admin cannot delete - different company")
            elif user_role == UserRole.STAFF.value:
                # 직원은 자신이 생성한 캠페인만 삭제 가능
                if campaign.creator_id == user_id:
                    can_delete = True
                    print(f"[CAMPAIGN-DELETE] Staff can delete own campaign")
                else:
                    print(f"[CAMPAIGN-DELETE] Staff cannot delete - not creator")
            elif user_role == UserRole.CLIENT.value:
                # 클라이언트는 자신의 회사와 연결된 캠페인만 삭제 가능 (제한적)
                if campaign.creator and campaign.creator.company == viewer.company:
                    can_delete = True
                    print(f"[CAMPAIGN-DELETE] Client can delete campaign from same company")
                else:
                    print(f"[CAMPAIGN-DELETE] Client cannot delete - different company")
            
            if not can_delete:
                print(f"[CAMPAIGN-DELETE] Permission denied for user_role={user_role}, creator_id={campaign.creator_id}")
                raise HTTPException(status_code=403, detail="이 캠페인을 삭제할 권한이 없습니다.")
            
            # 관련 데이터 확인 (구매요청 등)
            from app.models.purchase_request import PurchaseRequest
            purchase_query = select(PurchaseRequest).where(PurchaseRequest.campaign_id == campaign_id)
            purchase_result = await db.execute(purchase_query)
            purchase_requests = purchase_result.scalars().all()
            
            if purchase_requests:
                print(f"[CAMPAIGN-DELETE] Found {len(purchase_requests)} related purchase requests")
                # 구매요청이 있는 경우 경고하지만 삭제는 허용 (CASCADE)
                
            # 캠페인 삭제 (관련 데이터는 CASCADE로 자동 삭제)
            await db.delete(campaign)
            await db.commit()
            
            print(f"[CAMPAIGN-DELETE] SUCCESS: Campaign {campaign_id} deleted by user {user_id}")
            
            # WebSocket 알림 전송 (선택적)
            try:
                await manager.notify_campaign_update(
                    action="deleted",
                    campaign_id=campaign_id,
                    campaign_name=campaign.name,
                    user_id=user_id,
                    user_name=viewer.name
                )
                print(f"[CAMPAIGN-DELETE] WebSocket notification sent")
            except Exception as ws_error:
                print(f"[CAMPAIGN-DELETE] WebSocket notification failed: {ws_error}")
                # WebSocket 실패는 삭제 작업에 영향 없음
            
            print(f"[CAMPAIGN-DELETE] 🔴 END Request {request_id} - SUCCESS at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            return  # 204 No Content

        except HTTPException:
            print(f"[CAMPAIGN-DELETE] 🔴 END Request {request_id} - HTTP ERROR at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            raise
        except Exception as e:
            print(f"[CAMPAIGN-DELETE] 🔴 END Request {request_id} - EXCEPTION at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            print(f"[CAMPAIGN-DELETE] Unexpected error: {type(e).__name__}: {e}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"캠페인 삭제 중 오류: {str(e)}")
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        try:
            print(f"[CAMPAIGN-DELETE-JWT] 🟢 START JWT Request {request_id} at {timestamp}")
            print(f"[CAMPAIGN-DELETE-JWT] Request from user: {current_user.name}, role: {current_user.role.value}")
            print(f"[CAMPAIGN-DELETE-JWT] User details - ID: {current_user.id}, Company: {current_user.company}")

            # 캠페인 찾기 (creator 관계 포함)
            campaign_query = select(Campaign).options(joinedload(Campaign.creator)).where(Campaign.id == campaign_id)
            result = await db.execute(campaign_query)
            campaign = result.unique().scalar_one_or_none()

            if not campaign:
                print(f"[CAMPAIGN-DELETE-JWT] Campaign not found: {campaign_id}")
                raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다.")

            print(f"[CAMPAIGN-DELETE-JWT] Found campaign: {campaign.name}, creator_id={campaign.creator_id}")
            print(f"[CAMPAIGN-DELETE-JWT] Campaign creator info: {campaign.creator.name if campaign.creator else 'None'}, company: {campaign.creator.company if campaign.creator else 'None'}")

            # 권한 검사
            can_delete = False

            print(f"[CAMPAIGN-DELETE-JWT] Permission check starting...")
            print(f"[CAMPAIGN-DELETE-JWT] Current user role: {current_user.role} (enum: {current_user.role.value})")
            print(f"[CAMPAIGN-DELETE-JWT] Available roles: SUPER_ADMIN={UserRole.SUPER_ADMIN.value}, AGENCY_ADMIN={UserRole.AGENCY_ADMIN.value}, STAFF={UserRole.STAFF.value}, CLIENT={UserRole.CLIENT.value}")

            if current_user.role == UserRole.SUPER_ADMIN:
                # 슈퍼 어드민은 모든 캠페인 삭제 가능
                can_delete = True
                print(f"[CAMPAIGN-DELETE-JWT] ✅ Super admin can delete any campaign")
            elif current_user.role == UserRole.AGENCY_ADMIN:
                # 대행사 어드민은 같은 회사의 모든 캠페인 삭제 가능
                print(f"[CAMPAIGN-DELETE-JWT] Agency admin check - User company: '{current_user.company}', Campaign creator company: '{campaign.creator.company if campaign.creator else 'None'}'")
                if campaign.creator and campaign.creator.company == current_user.company:
                    can_delete = True
                    print(f"[CAMPAIGN-DELETE-JWT] ✅ Agency admin can delete campaign from same company")
                else:
                    print(f"[CAMPAIGN-DELETE-JWT] ❌ Agency admin cannot delete - different company")
            elif current_user.role == UserRole.STAFF:
                # 직원은 자신이 생성한 캠페인만 삭제 가능
                print(f"[CAMPAIGN-DELETE-JWT] Staff check - User ID: {current_user.id}, Campaign creator ID: {campaign.creator_id}")
                if campaign.creator_id == current_user.id:
                    can_delete = True
                    print(f"[CAMPAIGN-DELETE-JWT] ✅ Staff can delete own campaign")
                else:
                    print(f"[CAMPAIGN-DELETE-JWT] ❌ Staff cannot delete - not creator")
            elif current_user.role == UserRole.CLIENT:
                # 클라이언트는 자신의 회사와 연결된 캠페인만 삭제 가능 (제한적)
                print(f"[CAMPAIGN-DELETE-JWT] Client check - User company: '{current_user.company}', Campaign creator company: '{campaign.creator.company if campaign.creator else 'None'}'")
                if campaign.creator and campaign.creator.company == current_user.company:
                    can_delete = True
                    print(f"[CAMPAIGN-DELETE-JWT] ✅ Client can delete campaign from same company")
                else:
                    print(f"[CAMPAIGN-DELETE-JWT] ❌ Client cannot delete - different company")
            else:
                print(f"[CAMPAIGN-DELETE-JWT] ❌ Unknown role: {current_user.role}")

            print(f"[CAMPAIGN-DELETE-JWT] Final permission result: can_delete = {can_delete}")

            if not can_delete:
                print(f"[CAMPAIGN-DELETE-JWT] Permission denied for user_role={current_user.role.value}, creator_id={campaign.creator_id}")
                raise HTTPException(status_code=403, detail="이 캠페인을 삭제할 권한이 없습니다.")

            # 관련 데이터 확인 (구매요청 등)
            from app.models.purchase_request import PurchaseRequest
            purchase_query = select(PurchaseRequest).where(PurchaseRequest.campaign_id == campaign_id)
            purchase_result = await db.execute(purchase_query)
            purchase_requests = purchase_result.scalars().all()

            if purchase_requests:
                print(f"[CAMPAIGN-DELETE-JWT] Found {len(purchase_requests)} related purchase requests")
                # 구매요청이 있는 경우 경고하지만 삭제는 허용 (CASCADE)

            # 캠페인 삭제 (관련 데이터는 CASCADE로 자동 삭제)
            await db.delete(campaign)
            await db.commit()

            print(f"[CAMPAIGN-DELETE-JWT] SUCCESS: Campaign {campaign_id} deleted by user {current_user.id}")

            # WebSocket 알림 전송 (선택적)
            try:
                await manager.notify_campaign_update(
                    action="deleted",
                    campaign_id=campaign_id,
                    campaign_name=campaign.name,
                    user_id=current_user.id,
                    user_name=current_user.name
                )
                print(f"[CAMPAIGN-DELETE-JWT] WebSocket notification sent")
            except Exception as ws_error:
                print(f"[CAMPAIGN-DELETE-JWT] WebSocket notification failed: {ws_error}")
                # WebSocket 실패는 삭제 작업에 영향 없음

            print(f"[CAMPAIGN-DELETE-JWT] 🔴 END JWT Request {request_id} - SUCCESS at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            return  # 204 No Content

        except HTTPException:
            print(f"[CAMPAIGN-DELETE-JWT] 🔴 END JWT Request {request_id} - HTTP ERROR at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            raise
        except Exception as e:
            print(f"[CAMPAIGN-DELETE-JWT] 🔴 END JWT Request {request_id} - EXCEPTION at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            print(f"[CAMPAIGN-DELETE-JWT] Unexpected error: {type(e).__name__}: {e}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"캠페인 삭제 중 오류: {str(e)}")


# 발주요청 관련 엔드포인트
@router.post("/{campaign_id}/posts/{post_id}/order-request")
async def create_order_request(
    campaign_id: int,
    post_id: int,
    order_data: OrderRequestCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """JWT 기반 발주요청 생성"""

    print(f"[ORDER-REQUEST] Creating order request for post_id={post_id}, user_id={current_user.id}")

    try:
        # 포스트 존재 여부 및 권한 확인
        post_query = select(Post).where(
            Post.id == post_id,
            Post.campaign_id == campaign_id,
            Post.is_active == True
        )
        result = await db.execute(post_query)
        post = result.scalar_one_or_none()

        if not post:
            raise HTTPException(status_code=404, detail="포스트를 찾을 수 없습니다")

        # 제품 정보 조회 (cost_price 자동 계산용)
        from app.models.product import Product
        product_query = select(Product).where(Product.id == post.product_id)
        product_result = await db.execute(product_query)
        product = product_result.scalar_one_or_none()

        # cost_price 자동 계산: products.cost × posts.quantity
        calculated_cost_price = 0
        if product and product.cost and post.quantity:
            calculated_cost_price = int(product.cost * post.quantity)
            print(f"[ORDER-REQUEST] Auto-calculated cost_price: {product.cost} × {post.quantity} = {calculated_cost_price}")

        # 발주요청 생성
        new_order_request = OrderRequest(
            title=order_data.title,
            description=order_data.description,
            cost_price=calculated_cost_price,  # 자동 계산된 값 사용
            resource_type=order_data.resource_type,
            post_id=post_id,
            user_id=current_user.id,
            campaign_id=campaign_id,
            status="대기"
        )

        db.add(new_order_request)
        await db.commit()
        await db.refresh(new_order_request)

        # 포스트 상태 업데이트 (order_request_id 연결하지 않음)
        post.order_request_status = "발주 대기"
        await db.commit()

        print(f"[ORDER-REQUEST] Order request created successfully: {new_order_request.id}")

        # 응답 데이터 구성
        return {
            "id": new_order_request.id,
            "title": new_order_request.title,
            "description": new_order_request.description,
            "status": new_order_request.status,
            "cost_price": new_order_request.cost_price,
            "resource_type": new_order_request.resource_type,
            "post_id": new_order_request.post_id,
            "user_id": new_order_request.user_id,
            "campaign_id": new_order_request.campaign_id,
            "created_at": new_order_request.created_at.isoformat(),
            "updated_at": new_order_request.updated_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ORDER-REQUEST] Error creating order request: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"발주요청 생성 중 오류가 발생했습니다: {str(e)}")


@router.get("/{campaign_id}/posts/{post_id}/order-request")
async def get_order_request(
    campaign_id: int,
    post_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """JWT 기반 발주요청 조회"""

    try:
        # 발주요청 조회
        order_query = select(OrderRequest).where(
            OrderRequest.post_id == post_id,
            OrderRequest.campaign_id == campaign_id,
            OrderRequest.is_active == True
        ).order_by(OrderRequest.created_at.desc())

        result = await db.execute(order_query)
        order_request = result.scalar_one_or_none()

        if not order_request:
            raise HTTPException(status_code=404, detail="발주요청을 찾을 수 없습니다")

        return {
            "id": order_request.id,
            "title": order_request.title,
            "description": order_request.description,
            "status": order_request.status,
            "cost_price": order_request.cost_price,
            "resource_type": order_request.resource_type,
            "post_id": order_request.post_id,
            "user_id": order_request.user_id,
            "campaign_id": order_request.campaign_id,
            "created_at": order_request.created_at.isoformat(),
            "updated_at": order_request.updated_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ORDER-REQUEST] Error getting order request: {e}")
        raise HTTPException(status_code=500, detail=f"발주요청 조회 중 오류가 발생했습니다: {str(e)}")


@router.post("/update-order-cost-prices")
async def update_order_cost_prices(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """기존 order_requests의 cost_price를 products.cost × posts.quantity로 업데이트"""
    try:
        from sqlalchemy import text

        # 모든 활성 order_requests의 cost_price 업데이트
        update_query = text("""
            UPDATE order_requests
            SET cost_price = COALESCE(products.cost, 0) * COALESCE(posts.quantity, 1)
            FROM posts, products
            WHERE order_requests.post_id = posts.id
            AND posts.product_id = products.id
            AND order_requests.is_active = true
            AND posts.is_active = true
            AND products.is_active = true
        """)

        result = await db.execute(update_query)
        await db.commit()

        print(f"[UPDATE-COST-PRICES] Updated {result.rowcount} order_requests")

        return {
            "message": "order_requests cost_price 업데이트 완료",
            "updated_count": result.rowcount
        }

    except Exception as e:
        print(f"[UPDATE-COST-PRICES] Error: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"cost_price 업데이트 중 오류: {str(e)}")



@router.get("/debug-order-requests")
async def debug_order_requests(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """디버그: OrderRequest 테이블 데이터 확인"""
    try:
        from sqlalchemy import select
        from app.models.order_request import OrderRequest

        # 전체 OrderRequest 개수 확인
        count_query = select(OrderRequest.id).limit(10)
        result = await db.execute(count_query)
        orders = result.scalars().all()

        # 상태별 개수 확인
        status_query = select(OrderRequest.status, OrderRequest.id)
        status_result = await db.execute(status_query)
        status_data = status_result.all()

        return {
            "total_order_requests": len(orders),
            "sample_order_ids": orders,
            "status_data": [{"status": row.status, "id": row.id} for row in status_data],
            "success": True
        }

    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "success": False
        }


@router.get("/debug-amounts")
async def debug_amounts(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """임시 디버그 엔드포인트: 현재 vs 변경 후 금액 비교"""
    try:
        from sqlalchemy import text
        from datetime import datetime

        # 현재 날짜 기준 이번 달
        current_date = datetime.now()
        current_month = current_date.month
        current_year = current_date.year

        # 1. 현재 purchase_requests (이번 달 전체)
        purchase_query = text("""
            SELECT
                COUNT(*) as total_count,
                COALESCE(SUM(amount), 0) as total_amount
            FROM purchase_requests
            WHERE EXTRACT(MONTH FROM created_at) = :month
            AND EXTRACT(YEAR FROM created_at) = :year
        """)

        purchase_result = await db.execute(purchase_query, {"month": current_month, "year": current_year})
        purchase_row = purchase_result.fetchone()

        # 2. order_requests (이번 달 전체)
        order_all_query = text("""
            SELECT
                COUNT(*) as total_count,
                COALESCE(SUM(cost_price), 0) as total_amount
            FROM order_requests
            WHERE EXTRACT(MONTH FROM created_at) = :month
            AND EXTRACT(YEAR FROM created_at) = :year
            AND is_active = true
        """)

        order_all_result = await db.execute(order_all_query, {"month": current_month, "year": current_year})
        order_all_row = order_all_result.fetchone()

        # 3. order_requests (이번 달 승인된 것만)
        order_approved_query = text("""
            SELECT
                COUNT(*) as approved_count,
                COALESCE(SUM(cost_price), 0) as approved_amount
            FROM order_requests
            WHERE EXTRACT(MONTH FROM created_at) = :month
            AND EXTRACT(YEAR FROM created_at) = :year
            AND status = '승인'
            AND is_active = true
        """)

        order_approved_result = await db.execute(order_approved_query, {"month": current_month, "year": current_year})
        order_approved_row = order_approved_result.fetchone()

        # 4. order_requests 상태별 분포
        status_query = text("""
            SELECT
                status,
                COUNT(*) as count,
                COALESCE(SUM(cost_price), 0) as amount
            FROM order_requests
            WHERE EXTRACT(MONTH FROM created_at) = :month
            AND EXTRACT(YEAR FROM created_at) = :year
            AND is_active = true
            GROUP BY status
            ORDER BY status
        """)

        status_result = await db.execute(status_query, {"month": current_month, "year": current_year})
        status_rows = status_result.fetchall()

        return {
            "debug_date": f"{current_year}-{current_month:02d}",
            "current_purchase_requests": {
                "count": purchase_row[0] if purchase_row else 0,
                "amount": float(purchase_row[1]) if purchase_row else 0
            },
            "order_requests_all": {
                "count": order_all_row[0] if order_all_row else 0,
                "amount": float(order_all_row[1]) if order_all_row else 0
            },
            "order_requests_approved_only": {
                "count": order_approved_row[0] if order_approved_row else 0,
                "amount": float(order_approved_row[1]) if order_approved_row else 0
            },
            "order_requests_by_status": [
                {
                    "status": row[0],
                    "count": row[1],
                    "amount": float(row[2])
                }
                for row in status_rows
            ]
        }

    except Exception as e:
        print(f"[DEBUG-AMOUNTS] Error: {e}")
        raise HTTPException(status_code=500, detail=f"디버그 쿼리 실행 중 오류: {str(e)}")


@router.put("/{campaign_id}/reset-order-requests")
async def reset_campaign_order_requests(
    campaign_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    캠페인 수정 시 해당 캠페인의 모든 posts의 발주 요청 상태를 초기화합니다.
    """
    try:
        print(f"[RESET-ORDER-REQUESTS] Starting reset for campaign {campaign_id} by user {current_user.id}")

        # 캠페인 존재 확인
        campaign_query = select(Campaign).where(Campaign.id == campaign_id)
        campaign_result = await db.execute(campaign_query)
        campaign = campaign_result.scalar_one_or_none()

        if not campaign:
            raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다.")

        # 권한 확인 (캠페인을 수정할 수 있는 권한이 있는지 확인)
        user_role = current_user.role
        user_id = current_user.id

        can_reset = False
        if user_role == UserRole.SUPER_ADMIN.value:
            can_reset = True
            print(f"[RESET-ORDER-REQUESTS] SUPER_ADMIN access granted")
        elif user_role == UserRole.AGENCY_ADMIN.value:
            # creator를 직접 조회해서 확인
            creator_query = select(User).where(User.id == campaign.creator_id)
            creator_result = await db.execute(creator_query)
            creator = creator_result.scalar_one_or_none()

            if creator and creator.company == current_user.company:
                can_reset = True
                print(f"[RESET-ORDER-REQUESTS] AGENCY_ADMIN access granted: same company")
            else:
                print(f"[RESET-ORDER-REQUESTS] AGENCY_ADMIN access denied: different company or no creator")
        elif user_role == UserRole.STAFF.value:
            if campaign.creator_id == user_id:
                can_reset = True
                print(f"[RESET-ORDER-REQUESTS] STAFF access granted: campaign creator")
            else:
                print(f"[RESET-ORDER-REQUESTS] STAFF access denied: not campaign creator")

        if not can_reset:
            print(f"[RESET-ORDER-REQUESTS] Access denied for user {user_id} with role {user_role}")
            raise HTTPException(status_code=403, detail="이 캠페인의 발주 요청을 초기화할 권한이 없습니다.")

        # 해당 캠페인의 모든 posts의 발주 요청 상태 초기화
        from app.models.post import Post

        # 먼저 현재 상태 확인
        check_query = select(Post).where(Post.campaign_id == campaign_id)
        check_result = await db.execute(check_query)
        posts_before = check_result.scalars().all()

        print(f"[RESET-ORDER-REQUESTS] Found {len(posts_before)} posts for campaign {campaign_id}")
        for post in posts_before:
            print(f"[RESET-ORDER-REQUESTS] Post {post.id}: order_request_status={post.order_request_status}, order_request_id={post.order_request_id}")

        update_query = (
            update(Post)
            .where(Post.campaign_id == campaign_id)
            .values(
                order_request_status=None,
                order_request_id=None
            )
        )

        result = await db.execute(update_query)
        await db.commit()

        updated_count = result.rowcount
        print(f"[RESET-ORDER-REQUESTS] Update query executed, affected rows: {updated_count}")

        # 업데이트 후 상태 확인
        check_after_query = select(Post).where(Post.campaign_id == campaign_id)
        check_after_result = await db.execute(check_after_query)
        posts_after = check_after_result.scalars().all()

        print(f"[RESET-ORDER-REQUESTS] After update:")
        for post in posts_after:
            print(f"[RESET-ORDER-REQUESTS] Post {post.id}: order_request_status={post.order_request_status}, order_request_id={post.order_request_id}")

        return {
            "success": True,
            "message": f"캠페인 {campaign.name}의 {updated_count}개 업무의 발주 요청 상태가 초기화되었습니다.",
            "updated_count": updated_count
        }

    except HTTPException as e:
        print(f"[RESET-ORDER-REQUESTS] HTTP Error: {e.detail}")
        raise e
    except Exception as e:
        print(f"[RESET-ORDER-REQUESTS] Error: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"발주 요청 상태 초기화 중 오류가 발생했습니다: {str(e)}")


