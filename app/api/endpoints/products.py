from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional, List
from urllib.parse import unquote
from pydantic import BaseModel

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.models.product import Product
from app.models.work_type import WorkType

router = APIRouter()


# Pydantic 스키마
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    sku: Optional[str] = None
    category: Optional[str] = None  # work_type name for backwards compatibility
    work_type_id: Optional[int] = None  # work_type ID
    costPrice: float
    sellingPrice: Optional[float] = None
    unit: str = "건"
    minQuantity: int = 1
    maxQuantity: Optional[int] = None
    tags: Optional[str] = ""


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


@router.post("/", response_model=dict)
async def create_product(
    product_data: ProductCreate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """새 상품 생성"""
    print(f"[PRODUCT-CREATE] Creating product: {product_data.dict()}")

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

        print(f"[PRODUCT-CREATE] Node.js API mode - user_id={user_id}, role={user_role}")

    else:
        # JWT 기반 모드
        current_user = jwt_user
        user_role = current_user.role.value

        print(f"[PRODUCT-CREATE] JWT mode - user_id={current_user.id}, role={user_role}")

    try:
        # work_type 처리 - category name으로 work_type_id 찾기
        work_type_id = product_data.work_type_id
        if product_data.category and not work_type_id:
            work_type_query = select(WorkType).where(
                WorkType.name == product_data.category,
                WorkType.is_active == True
            )
            result = await db.execute(work_type_query)
            work_type = result.scalar_one_or_none()
            if work_type:
                work_type_id = work_type.id

        # SKU 중복 확인
        if product_data.sku:
            existing_sku_query = select(Product).where(Product.sku == product_data.sku)
            result = await db.execute(existing_sku_query)
            existing_product = result.scalar_one_or_none()
            if existing_product:
                raise HTTPException(status_code=400, detail="이미 존재하는 SKU입니다")

        # 새 상품 생성
        new_product = Product(
            name=product_data.name,
            description=product_data.description or "",
            price=product_data.costPrice,  # cost price를 price 필드에 저장
            cost=product_data.costPrice,   # 호환성을 위해 cost도 저장
            selling_price=product_data.sellingPrice,
            category=product_data.category,  # 호환성을 위해 보존
            work_type_id=work_type_id,
            sku=product_data.sku,
            unit=product_data.unit,
            min_quantity=product_data.minQuantity,
            max_quantity=product_data.maxQuantity,
            tags=product_data.tags,
            is_active=True
        )

        db.add(new_product)
        await db.commit()
        await db.refresh(new_product)

        # work_type 정보를 포함해서 응답
        await db.refresh(new_product, ["work_type"])

        print(f"[PRODUCT-CREATE] SUCCESS: Created product {new_product.id} by user {current_user.id}")

        return {
            "id": new_product.id,
            "name": new_product.name,
            "description": new_product.description,
            "category": new_product.work_type.name if new_product.work_type else new_product.category,
            "work_type_id": new_product.work_type_id,
            "sku": new_product.sku,
            "costPrice": new_product.price,
            "sellingPrice": new_product.selling_price,
            "unit": new_product.unit,
            "minQuantity": new_product.min_quantity,
            "maxQuantity": new_product.max_quantity,
            "tags": new_product.tags,
            "isActive": new_product.is_active,
            "createdAt": new_product.created_at.isoformat() if new_product.created_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PRODUCT-CREATE] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"상품 생성 중 오류: {str(e)}")