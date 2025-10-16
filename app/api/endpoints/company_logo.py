from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from urllib.parse import unquote
from datetime import datetime

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.company_logo import CompanyLogo
from app.core.file_upload import file_manager

router = APIRouter()


@router.get("/logo")
async def get_company_logo(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
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
        current_user = jwt_user
        print(f"[COMPANY-LOGO-GET-JWT] Request from user_id={current_user.id}, user_role={current_user.role}")
        
        try:
            company_name = current_user.company or 'default'
            
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
                    "updatedBy": current_user.id
                }
            
            print(f"[COMPANY-LOGO-GET-JWT] SUCCESS: Found logo for company {company_name}")
            return {
                "id": logo_data.id,
                "logoUrl": logo_data.logo_url,
                "uploadedAt": logo_data.uploaded_at.isoformat() if logo_data.uploaded_at else None,
                "companyId": logo_data.company_id,
                "updatedBy": logo_data.updated_by
            }
            
        except Exception as e:
            print(f"[COMPANY-LOGO-GET-JWT] Unexpected error: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"로고 조회 중 오류: {str(e)}")


@router.post("/logo")
async def upload_company_logo(
    logo: UploadFile = File(...),
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """회사 로고 업로드 (파일 기반)"""
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

        # 사용자의 회사 정보 찾기
        user_query = select(User).where(User.id == user_id)
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

        company_name = user.company or 'default'

        # 파일 업로드
        file_result = await file_manager.save_file(logo)
        logo_url = file_result["url"]

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
        current_user = jwt_user
        print(f"[COMPANY-LOGO-UPLOAD-JWT] Request from user_id={current_user.id}, user_role={current_user.role}")

        try:
            # 권한 확인: 대행사 어드민만 로고 업로드 가능
            if current_user.role.value not in ['AGENCY_ADMIN', 'SUPER_ADMIN']:
                raise HTTPException(status_code=403, detail="권한이 없습니다. 대행사 어드민만 로고를 업로드할 수 있습니다.")

            company_name = current_user.company or 'default'

            # 파일 업로드
            file_result = await file_manager.save_file(logo)
            logo_url = file_result["url"]

            # 기존 로고 확인
            existing_logo_query = select(CompanyLogo).where(CompanyLogo.company_id == company_name)
            existing_result = await db.execute(existing_logo_query)
            existing_logo = existing_result.scalar_one_or_none()

            if existing_logo:
                # 기존 로고 업데이트
                existing_logo.logo_url = logo_url
                existing_logo.uploaded_at = datetime.utcnow()
                existing_logo.updated_by = current_user.id
                await db.commit()
                await db.refresh(existing_logo)

                print(f"[COMPANY-LOGO-UPLOAD-JWT] SUCCESS: Updated logo for company {company_name}")

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
                    updated_by=current_user.id
                )

                db.add(new_logo)
                await db.commit()
                await db.refresh(new_logo)

                print(f"[COMPANY-LOGO-UPLOAD-JWT] SUCCESS: Created new logo for company {company_name}")

                return {
                    "id": new_logo.id,
                    "logoUrl": new_logo.logo_url,
                    "uploadedAt": new_logo.uploaded_at.isoformat(),
                    "companyId": new_logo.company_id,
                    "updatedBy": new_logo.updated_by
                }

        except HTTPException:
            raise
        except Exception as e:
            print(f"[COMPANY-LOGO-UPLOAD-JWT] Unexpected error: {type(e).__name__}: {e}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"로고 업로드 중 오류: {str(e)}")


@router.delete("/logo")
async def delete_company_logo(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
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
        current_user = jwt_user
        print(f"[COMPANY-LOGO-DELETE-JWT] Request from user_id={current_user.id}, user_role={current_user.role}")
        
        try:
            # 권한 확인: 대행사 어드민만 로고 제거 가능
            if current_user.role.value not in ['AGENCY_ADMIN', 'SUPER_ADMIN']:
                raise HTTPException(status_code=403, detail="권한이 없습니다. 대행사 어드민만 로고를 제거할 수 있습니다.")
            
            company_name = current_user.company or 'default'
            
            # 해당 회사의 로고 제거
            logo_query = select(CompanyLogo).where(CompanyLogo.company_id == company_name)
            logo_result = await db.execute(logo_query)
            logo = logo_result.scalar_one_or_none()
            
            if logo:
                await db.delete(logo)
                await db.commit()
                print(f"[COMPANY-LOGO-DELETE-JWT] SUCCESS: Deleted logo for company {company_name}")
            else:
                print(f"[COMPANY-LOGO-DELETE-JWT] No logo found for company {company_name}")
            
            return {"message": "로고가 제거되었습니다."}
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"[COMPANY-LOGO-DELETE-JWT] Unexpected error: {type(e).__name__}: {e}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"로고 제거 중 오류: {str(e)}")