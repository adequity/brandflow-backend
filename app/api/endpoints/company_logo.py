from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from urllib.parse import unquote
from datetime import datetime

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.company_logo import CompanyLogo

router = APIRouter()


@router.get("/logo")
async def get_company_logo(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """회사 로고 조회 (대행사별)"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 사용자의 회사 정보 찾기
        user_query = select(User).where(User.id == user_id)
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        company_name = user.company or 'default'
        
        # 해당 회사의 로고 데이터 조회
        logo_query = select(CompanyLogo).where(CompanyLogo.company_id == company_name)
        logo_result = await db.execute(logo_query)
        logo_data = logo_result.scalar_one_or_none()
        
        if not logo_data:
            # 로고가 없으면 기본 데이터 반환
            return {
                "id": 1,
                "logoUrl": None,
                "uploadedAt": None,
                "companyId": company_name,
                "updatedBy": user_id
            }
        
        return {
            "id": logo_data.id,
            "logoUrl": logo_data.logo_url,
            "uploadedAt": logo_data.uploaded_at.isoformat() if logo_data.uploaded_at else None,
            "companyId": logo_data.company_id,
            "updatedBy": logo_data.updated_by
        }
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 회사 로고 조회 구현
        raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/logo")
async def upload_company_logo(
    logo_data: dict,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """회사 로고 업로드"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 권한 확인: 대행사 어드민만 로고 업로드 가능
        is_agency_admin = (user_role == '대행사 어드민' or 
                         user_role == '대행사어드민' or
                         ('대행사' in user_role and '어드민' in user_role))
        
        if not is_agency_admin:
            raise HTTPException(status_code=403, detail="권한이 없습니다. 대행사 어드민만 로고를 업로드할 수 있습니다.")
        
        logo_url = logo_data.get('logoUrl')
        
        if not logo_url:
            raise HTTPException(status_code=400, detail="로고 URL이 필요합니다.")
        
        # 사용자의 회사 정보 찾기
        user_query = select(User).where(User.id == user_id)
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        company_name = user.company or 'default'
        
        # 기존 로고 확인
        existing_logo_query = select(CompanyLogo).where(CompanyLogo.company_id == company_name)
        existing_result = await db.execute(existing_logo_query)
        existing_logo = existing_result.scalar_one_or_none()
        
        if existing_logo:
            # 기존 로고 업데이트
            existing_logo.logo_url = logo_url
            existing_logo.uploaded_at = datetime.utcnow()
            existing_logo.updated_by = user_id
            await db.commit()
            await db.refresh(existing_logo)
            
            return {
                "id": existing_logo.id,
                "logoUrl": existing_logo.logo_url,
                "uploadedAt": existing_logo.uploaded_at.isoformat(),
                "companyId": existing_logo.company_id,
                "updatedBy": existing_logo.updated_by
            }
        else:
            # 새 로고 생성
            new_logo = CompanyLogo(
                logo_url=logo_url,
                uploaded_at=datetime.utcnow(),
                company_id=company_name,
                updated_by=user_id
            )
            
            db.add(new_logo)
            await db.commit()
            await db.refresh(new_logo)
            
            return {
                "id": new_logo.id,
                "logoUrl": new_logo.logo_url,
                "uploadedAt": new_logo.uploaded_at.isoformat(),
                "companyId": new_logo.company_id,
                "updatedBy": new_logo.updated_by
            }
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 회사 로고 업로드 구현
        raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete("/logo")
async def delete_company_logo(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db)
):
    """회사 로고 제거 (대행사별)"""
    # Node.js API 호환 모드인지 확인
    if viewerId is not None or adminId is not None:
        # Node.js API 호환 모드
        user_id = viewerId or adminId
        user_role = viewerRole or adminRole
        
        if not user_id or not user_role:
            raise HTTPException(status_code=400, detail="viewerId와 viewerRole이 필요합니다")
        
        # URL 디코딩
        user_role = unquote(user_role).strip()
        
        # 권한 확인: 대행사 어드민만 로고 제거 가능
        is_agency_admin = (user_role == '대행사 어드민' or 
                         user_role == '대행사어드민' or
                         ('대행사' in user_role and '어드민' in user_role))
        
        if not is_agency_admin:
            raise HTTPException(status_code=403, detail="권한이 없습니다. 대행사 어드민만 로고를 제거할 수 있습니다.")
        
        # 사용자의 회사 정보 찾기
        user_query = select(User).where(User.id == user_id)
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        company_name = user.company or 'default'
        
        # 해당 회사의 로고 제거
        logo_query = select(CompanyLogo).where(CompanyLogo.company_id == company_name)
        logo_result = await db.execute(logo_query)
        logo = logo_result.scalar_one_or_none()
        
        if logo:
            await db.delete(logo)
            await db.commit()
        
        return {"message": "로고가 제거되었습니다."}
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = await get_current_active_user()
        # TODO: 기존 방식으로 회사 로고 제거 구현
        raise HTTPException(status_code=501, detail="Not implemented yet")