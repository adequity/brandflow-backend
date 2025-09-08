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
from app.models.user import User
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
        
        result = await db.execute(query)
        campaigns = result.unique().scalars().all()  # unique() 추가로 중복 제거
        
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
        
        if not (is_admin or is_staff):
            raise HTTPException(status_code=403, detail="권한이 없습니다. 관리자와 직원만 캠페인을 생성할 수 있습니다.")
        
        # 새 캠페인 생성
        new_campaign = Campaign(
            name=campaign_data.name,
            description=campaign_data.description or '',
            client_company=campaign_data.client_company or "테스트 클라이언트",
            budget=campaign_data.budget or 0.0,
            start_date=campaign_data.start_date.replace(tzinfo=None) if campaign_data.start_date else datetime.now(timezone.utc).replace(tzinfo=None),
            end_date=campaign_data.end_date.replace(tzinfo=None) if campaign_data.end_date else datetime.now(timezone.utc).replace(tzinfo=None),
            creator_id=user_id,
            status=CampaignStatus.ACTIVE  # Enum 사용
        )
        
        db.add(new_campaign)
        await db.commit()
        await db.refresh(new_campaign)
        
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
                raise HTTPException(status_code=403, detail="자신이 생성한 캠페인만 접근할 수 있습니다.")
        
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
        
        for field, value in update_data.items():
            if field == 'user_id':
                # 클라이언트 ID는 변경 불가
                continue
            elif hasattr(campaign, field):
                setattr(campaign, field, value)
        
        # 업데이트 시간과 업데이트한 사용자 정보 추가
        campaign.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(campaign)
        
        return campaign
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
        
        # 재무 요약 데이터 (시연용)
        return {
            "campaign_id": campaign_id,
            "total_budget": float(campaign.budget) if campaign.budget else 0.0,
            "spent_amount": float(campaign.budget * 0.45) if campaign.budget else 0.0,
            "remaining_budget": float(campaign.budget * 0.55) if campaign.budget else 0.0,
            "expense_categories": {
                "광고비": float(campaign.budget * 0.25) if campaign.budget else 0.0,
                "제작비": float(campaign.budget * 0.15) if campaign.budget else 0.0,
                "기타": float(campaign.budget * 0.05) if campaign.budget else 0.0
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