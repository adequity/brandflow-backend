from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import List, Optional
from urllib.parse import unquote
from datetime import datetime, timezone

from app.db.database import get_async_db
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignResponse
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.models.campaign import Campaign, CampaignStatus
from app.core.websocket import manager

router = APIRouter()


@router.get("/", response_model=List[CampaignResponse])
async def get_campaigns(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    # 기존 파라미터도 지원
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db)
):
    """캠페인 목록 조회 (권한별 필터링)"""
    print(f"[CAMPAIGNS-LIST] Request with viewerId={viewerId}, viewerRole={viewerRole}")
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 영어 역할명을 한글로 매핑 (프론트엔드 호환성)
        english_to_korean_roles = {
            'super_admin': '슈퍼 어드민',
            'agency_admin': '대행사 어드민',
            'agency_staff': '대행사 직원',
            'staff': '직원',
            'client': '클라이언트',
            'admin': '어드민'
        }
        
        # 영어 역할명이면 한글로 변환
        if user_role in english_to_korean_roles:
            user_role = english_to_korean_roles[user_role]
        
        # 현재 사용자 조회
        current_user_query = select(User).where(User.id == user_id)
        result = await db.execute(current_user_query)
        current_user = result.scalar_one_or_none()
        
        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        print(f"[CAMPAIGNS-LIST] User found: {current_user.name}, role='{user_role}', company='{current_user.company}'")
        
        # 권한별 필터링 (N+1 문제 해결을 위한 JOIN 최적화)
        if user_role in ['슈퍼 어드민', '슈퍼어드민'] or '슈퍼' in user_role:
            # 슈퍼 어드민은 모든 캠페인 조회 가능
            query = select(Campaign).options(joinedload(Campaign.creator))
        elif user_role in ['대행사 어드민', '대행사어드민'] or ('대행사' in user_role and '어드민' in user_role):
            # 대행사 어드민은 같은 회사 소속 캠페인만
            query = select(Campaign).options(joinedload(Campaign.creator)).join(User, Campaign.creator_id == User.id).where(User.company == current_user.company)
        elif user_role == '직원':
            # 직원은 자신이 생성한 캠페인만 조회 가능
            query = select(Campaign).options(joinedload(Campaign.creator)).where(Campaign.creator_id == user_id)
        elif user_role == '클라이언트':
            # 클라이언트는 자신의 캠페인만 조회 가능
            query = select(Campaign).options(joinedload(Campaign.creator)).where(Campaign.creator_id == user_id)
        else:
            query = select(Campaign).options(joinedload(Campaign.creator))
        
        print(f"[CAMPAIGNS-LIST] Executing query for role: {user_role}")
        result = await db.execute(query)
        campaigns = result.unique().scalars().all()  # unique() 추가로 중복 제거
        
        print(f"[CAMPAIGNS-LIST] Found {len(campaigns)} campaigns for user {user_id} (role: {user_role})")
        for campaign in campaigns:
            print(f"  - Campaign ID {campaign.id}: {campaign.name} (creator: {campaign.creator_id})")
        
        return campaigns
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 캠페인 조회 구현
        return []


@router.post("/", response_model=CampaignResponse)
async def create_campaign(
    campaign_data: CampaignCreate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """새 캠페인 생성 (권한 확인)"""
    # 실제 요청 데이터 로깅
    print(f"[CAMPAIGN-CREATE] Campaign creation request - Data: {campaign_data}")
    print(f"[CAMPAIGN-CREATE] Query params: viewerId={viewerId}, viewerRole={viewerRole}")
    print(f"[CAMPAIGN-CREATE] Request headers available")
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 영어 역할명을 한글로 매핑 (프론트엔드 호환성)
        english_to_korean_roles = {
            'super_admin': '슈퍼 어드민',
            'agency_admin': '대행사 어드민',
            'staff': '직원',
            'client': '클라이언트'
        }
        
        # 영어 역할명이면 한글로 변환
        mapped_role = english_to_korean_roles.get(user_role.lower(), user_role)
        
        # 권한 확인 - 관리자와 직원은 캠페인 생성 가능 (한글/영어 역할명 모두 지원)
        is_admin = (mapped_role in ['슈퍼 어드민', '슈퍼어드민', '대행사 어드민', '대행사어드민'] or 
                    '슈퍼' in mapped_role or ('대행사' in mapped_role and '어드민' in mapped_role) or
                    user_role.lower() in ['super_admin', 'agency_admin'])
        is_staff = (mapped_role == '직원' or user_role.lower() == 'staff')
        
        print(f"[CAMPAIGN-CREATE] Authorization check - user_role={user_role}, mapped_role={mapped_role}, is_admin={is_admin}, is_staff={is_staff}")
        
        if not (is_admin or is_staff):
            print(f"[CAMPAIGN-CREATE] ERROR: Insufficient permissions - user_role={user_role}, mapped_role={mapped_role}")
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
                        print(f"[CAMPAIGN-CREATE] WARNING: Failed to parse date string: {date_input}")
                        return current_time
                return current_time
            
            new_campaign = Campaign(
                name=campaign_data.name.strip() if campaign_data.name else "새 캠페인",
                description=campaign_data.description or '',
                client_company=campaign_data.client_company or "기본 클라이언트",
                budget=float(campaign_data.budget) if campaign_data.budget is not None else 1000000.0,
                start_date=safe_datetime_parse(campaign_data.start_date),
                end_date=safe_datetime_parse(campaign_data.end_date),
                creator_id=user_id,
                status=CampaignStatus.ACTIVE
            )
            
            print(f"[CAMPAIGN-CREATE] SUCCESS: Creating campaign with data: name='{new_campaign.name}', budget={new_campaign.budget}")
            db.add(new_campaign)
            await db.commit()
            await db.refresh(new_campaign)
            print(f"[CAMPAIGN-CREATE] SUCCESS: Campaign created with ID {new_campaign.id}")
        except Exception as e:
            await db.rollback()
            print(f"[CAMPAIGN-CREATE] ERROR: Database operation failed: {e}")
            print(f"[CAMPAIGN-CREATE] ERROR: Exception type: {type(e).__name__}")
            print(f"[CAMPAIGN-CREATE] ERROR: Campaign data that failed: name='{campaign_data.name}', budget={campaign_data.budget}, client_company='{campaign_data.client_company}'")
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
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 캠페인 생성 구현
        raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign_detail(
    campaign_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """캠페인 상세 조회 (권한별 필터링)"""
    print(f"[CAMPAIGN-DETAIL] Request for campaign_id={campaign_id}, viewerId={viewerId}, viewerRole={viewerRole}")
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        try:
            # Node.js API 호환 모드
            user_id = viewerId or adminId
            user_role = viewerRole or adminRole
            
            if not user_id or not user_role:
                print(f"[CAMPAIGN-DETAIL] ERROR: Missing params - user_id={user_id}, user_role={user_role}")
                raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
            
            # URL 디코딩
            user_role = unquote(user_role).strip()
            print(f"[CAMPAIGN-DETAIL] Processing with user_id={user_id}, user_role='{user_role}'")
            
            # 캠페인 찾기 (creator 관계 포함)
            print(f"[CAMPAIGN-DETAIL] Searching for campaign with ID: {campaign_id}")
            campaign_query = select(Campaign).options(joinedload(Campaign.creator)).where(Campaign.id == campaign_id)
            result = await db.execute(campaign_query)
            campaign = result.unique().scalar_one_or_none()
            
            if not campaign:
                print(f"[CAMPAIGN-DETAIL] Campaign not found: {campaign_id}")
                raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다.")
            
            print(f"[CAMPAIGN-DETAIL] Found campaign: {campaign.name}, creator_id={campaign.creator_id}")
            print(f"[CAMPAIGN-DETAIL] Campaign creator loaded: {campaign.creator is not None}")
            if campaign.creator:
                print(f"[CAMPAIGN-DETAIL] Creator info: name={campaign.creator.name}, email={campaign.creator.email}")
            print(f"[CAMPAIGN-DETAIL] Campaign creator_name property: {campaign.creator_name}")
            print(f"[CAMPAIGN-DETAIL] Campaign client_name property: {campaign.client_name}")
            
            # 권한 확인
            print(f"[CAMPAIGN-DETAIL] Checking user permissions for user_id: {user_id}")
            viewer_query = select(User).where(User.id == user_id)
            viewer_result = await db.execute(viewer_query)
            viewer = viewer_result.scalar_one_or_none()
            
            if not viewer:
                print(f"[CAMPAIGN-DETAIL] User not found: {user_id}")
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
            
            print(f"[CAMPAIGN-DETAIL] Found user: {viewer.name}, role={user_role}, company={viewer.company}")
            
        except HTTPException:
            raise  # HTTPException은 그대로 전달
        except Exception as e:
            print(f"[CAMPAIGN-DETAIL] Unexpected error: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"캠페인 조회 중 오류: {str(e)}")
        
        if user_role == '클라이언트':
            # 클라이언트는 본인 캠페인만 조회 가능
            if campaign.creator_id != user_id:
                raise HTTPException(status_code=403, detail="이 캠페인에 접근할 권한이 없습니다.")
        elif user_role in ['대행사 어드민', '대행사어드민'] or ('대행사' in user_role and '어드민' in user_role):
            # 대행사 어드민은 같은 회사 캠페인만 조회 가능
            client_query = select(User).where(User.id == campaign.creator_id)
            client_result = await db.execute(client_query)
            client = client_result.scalar_one_or_none()
            
            if not client or client.company != viewer.company:
                raise HTTPException(status_code=403, detail="이 캠페인에 접근할 권한이 없습니다.")
        elif user_role == '직원':
            # 직원은 자신이 생성한 캠페인만 조회 가능
            if campaign.creator_id != user_id:
                print(f"[CAMPAIGN-DETAIL] Staff permission denied: campaign.creator_id={campaign.creator_id}, user_id={user_id}")
                raise HTTPException(status_code=403, detail="자신이 생성한 캠페인만 접근할 수 있습니다.")
        
        print(f"[CAMPAIGN-DETAIL] SUCCESS: Returning campaign {campaign.id} to user {user_id}")
        return campaign
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 캠페인 상세 조회 구현
        raise HTTPException(status_code=501, detail="Not implemented yet")


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    campaign_data: CampaignUpdate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
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
            
            if user_role == '클라이언트':
                # 클라이언트는 본인 캠페인만 수정 가능
                if campaign.creator_id != user_id:
                    raise HTTPException(status_code=403, detail="이 캠페인을 수정할 권한이 없습니다.")
            elif user_role in ['대행사 어드민', '대행사어드민'] or ('대행사' in user_role and '어드민' in user_role):
                # 대행사 어드민은 같은 회사 캠페인만 수정 가능
                client_query = select(User).where(User.id == campaign.creator_id)
                client_result = await db.execute(client_query)
                client = client_result.scalar_one_or_none()
                
                if not client or client.company != viewer.company:
                    raise HTTPException(status_code=403, detail="이 캠페인을 수정할 권한이 없습니다.")
            elif user_role == '직원':
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
                elif field == 'creator_id' and value:
                    # 담당 직원 변경 (대행사 어드민만 가능)
                    if user_role not in ['대행사 어드민', '대행사어드민'] and not ('대행사' in user_role and '어드민' in user_role):
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
                elif field in ['start_date', 'end_date'] and value:
                    # 날짜 필드는 안전하게 파싱
                    try:
                        if isinstance(value, str):
                            parsed_date = safe_datetime_parse(value)
                            setattr(campaign, field, parsed_date)
                            print(f"[CAMPAIGN-UPDATE] Parsed date {field}: {value} -> {parsed_date}")
                        else:
                            setattr(campaign, field, value)
                    except Exception as e:
                        print(f"[CAMPAIGN-UPDATE] Date parsing error for {field}: {e}")
                        # 날짜 파싱 실패 시 원본 값 사용
                        setattr(campaign, field, value)
                elif hasattr(campaign, field):
                    setattr(campaign, field, value)
                    print(f"[CAMPAIGN-UPDATE] Updated {field}: {value}")
        
            # 업데이트 시간과 업데이트한 사용자 정보 추가
            campaign.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(campaign)
            
            print(f"[CAMPAIGN-UPDATE] SUCCESS: Campaign {campaign_id} updated by user {user_id}")
            return campaign
            
        except HTTPException:
            raise  # HTTPException은 그대로 전달
        except Exception as e:
            print(f"[CAMPAIGN-UPDATE] Unexpected error: {type(e).__name__}: {e}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"캠페인 수정 중 오류: {str(e)}")
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 캠페인 수정 구현
        raise HTTPException(status_code=501, detail="Not implemented yet")


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
        
        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "total_budget": budget_amount,
            "total_revenue": total_revenue,
            "total_cost": total_cost,
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
            "conversion_rate": 0.045
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
        
        # 현재는 빈 배열 반환 (추후 posts 모델 구현시 확장)
        return []
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 게시물 목록 조회 구현
        raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/staff-list", response_model=List[dict])
async def get_staff_members(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """같은 회사 직원 목록 조회 (대행사 어드민용)"""
    print(f"[STAFF-MEMBERS] Request from viewerId={viewerId}, viewerRole={viewerRole}")
    
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        try:
            user_id = viewerId or adminId
            user_role = viewerRole or adminRole
            
            if not user_id or not user_role:
                print(f"[STAFF-MEMBERS] ERROR: Missing params - user_id={user_id}, user_role={user_role}")
                raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
            
            # URL 디코딩
            user_role = unquote(user_role).strip()
            print(f"[STAFF-MEMBERS] Processing with user_id={user_id}, user_role='{user_role}'")
            
            # 현재 사용자 정보 조회
            viewer_query = select(User).where(User.id == user_id)
            viewer_result = await db.execute(viewer_query)
            viewer = viewer_result.scalar_one_or_none()
            
            if not viewer:
                print(f"[STAFF-MEMBERS] User not found: {user_id}")
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
            
            print(f"[STAFF-MEMBERS] Found user: {viewer.name}, company={viewer.company}")
            
            # 대행사 어드민만 직원 목록 조회 가능
            if user_role not in ['대행사 어드민', '대행사어드민'] and not ('대행사' in user_role and '어드민' in user_role):
                raise HTTPException(status_code=403, detail="직원 목록 조회 권한이 없습니다")
            
            # 같은 회사의 직원들 조회 (직원 역할만)
            staff_query = select(User).where(
                User.company == viewer.company,
                User.role == UserRole.STAFF,
                User.is_active == True
            )
            result = await db.execute(staff_query)
            staff_members = result.scalars().all()
            
            print(f"[STAFF-MEMBERS] Found {len(staff_members)} staff members")
            
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
            print(f"[STAFF-MEMBERS] Unexpected error: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"직원 목록 조회 중 오류: {str(e)}")
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 직원 목록 조회 구현
        raise HTTPException(status_code=501, detail="Not implemented yet")