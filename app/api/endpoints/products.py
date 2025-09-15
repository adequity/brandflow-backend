from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from urllib.parse import unquote

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.product import Product

router = APIRouter()


@router.get("/", response_model=List[dict])
async def get_products(
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """상품 목록 조회"""
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
        
        # 모든 역할이 상품 목록 조회 가능
        products_query = select(Product)
        result = await db.execute(products_query)
        products = result.scalars().all()
        
        # 상품 정보 매핑 (Node.js API 호환성을 위해)
        products_data = []
        for product in products:
            product_data = {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": product.price,
                "category": product.category,
                "status": product.status
            }
            
            # selling_price나 cost_price가 있으면 추가
            if hasattr(product, 'selling_price') and product.selling_price:
                product_data["sellingPrice"] = product.selling_price
            if hasattr(product, 'cost_price') and product.cost_price:
                product_data["costPrice"] = product.cost_price
                
            products_data.append(product_data)
        
        return products_data
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = jwt_user
        print(f"[PRODUCTS-LIST-JWT] Request from user_id={current_user.id}, user_role={current_user.role}")
        
        try:
            # JWT 기반 상품 목록 조회
            query = select(Product)
            result = await db.execute(query)
            products = result.scalars().all()
            
            # 응답 데이터 구성
            products_data = []
            for product in products:
                product_data = {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "category": product.category,
                    "price": product.price,
                    "isActive": product.is_active,
                    "createdAt": product.created_at.isoformat() if product.created_at else None
                }
                
                # 추가 필드가 있다면 포함
                if hasattr(product, 'selling_price') and product.selling_price:
                    product_data["sellingPrice"] = product.selling_price
                if hasattr(product, 'cost_price') and product.cost_price:
                    product_data["costPrice"] = product.cost_price
                    
                products_data.append(product_data)
            
            print(f"[PRODUCTS-LIST-JWT] SUCCESS: Returning {len(products_data)} products")
            return products_data
            
        except Exception as e:
            print(f"[PRODUCTS-LIST-JWT] Unexpected error: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"상품 목록 조회 중 오류: {str(e)}")