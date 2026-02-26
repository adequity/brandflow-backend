from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional, List
from urllib.parse import unquote
from pydantic import BaseModel, field_validator

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

    @field_validator('sellingPrice', 'maxQuantity', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """빈 문자열을 None으로 변환"""
        if v == "" or v is None:
            return None
        return v


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None  # work_type name for backwards compatibility
    work_type_id: Optional[int] = None  # work_type ID
    costPrice: Optional[float] = None
    sellingPrice: Optional[float] = None
    unit: Optional[str] = None
    minQuantity: Optional[int] = None
    maxQuantity: Optional[int] = None
    tags: Optional[str] = None
    isActive: Optional[bool] = None

    @field_validator('costPrice', 'sellingPrice', 'minQuantity', 'maxQuantity', 'work_type_id', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """빈 문자열을 None으로 변환"""
        if v == "" or v is None:
            return None
        return v


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
        
        # 모든 역할이 상품 목록 조회 가능 (활성 상품만, 회사별 필터링)
        # company 필드가 None인 경우 기본값으로 처리
        user_company = current_user.company or 'default_company'
        products_query = select(Product).where(
            Product.is_active == True,
            (Product.company == user_company) | (Product.company.is_(None))
        )
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
                "costPrice": product.cost if hasattr(product, 'cost') else product.price,
                "sellingPrice": product.selling_price if hasattr(product, 'selling_price') else None,
                "unit": product.unit if hasattr(product, 'unit') else "건",
                "minQuantity": product.min_quantity if hasattr(product, 'min_quantity') else 1,
                "maxQuantity": product.max_quantity if hasattr(product, 'max_quantity') else None,
                "category": product.category,
                "sku": product.sku if hasattr(product, 'sku') else None,
                "isActive": product.is_active
            }

            products_data.append(product_data)
        
        return products_data
    else:
        # 기존 API 모드 (JWT 토큰 기반)
        current_user = jwt_user
        print(f"[PRODUCTS-LIST-JWT] Request from user_id={current_user.id}, user_role={current_user.role}, user_company={current_user.company}")

        try:
            # 먼저 모든 상품을 조회해서 company 값들을 확인
            all_products_query = select(Product).where(Product.is_active == True)
            all_result = await db.execute(all_products_query)
            all_products = all_result.scalars().all()

            print(f"[PRODUCTS-DEBUG] Total active products: {len(all_products)}")
            for product in all_products:
                print(f"[PRODUCTS-DEBUG] Product ID {product.id}: name='{product.name}', company='{product.company}'")

            # JWT 기반 상품 목록 조회 (활성 상품만, 회사별 필터링)
            # company 필드가 None인 경우 기본값으로 처리
            user_company = current_user.company or 'default_company'
            print(f"[PRODUCTS-FILTER] Filtering products for user_company: '{user_company}'")

            query = select(Product).where(
                Product.is_active == True,
                (Product.company == user_company) | (Product.company.is_(None))
            )
            result = await db.execute(query)
            products = result.scalars().all()

            print(f"[PRODUCTS-FILTER] Filtered products count: {len(products)}")
            
            # 응답 데이터 구성
            products_data = []
            for product in products:
                product_data = {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "category": product.category,
                    "price": product.price,
                    "costPrice": product.cost if hasattr(product, 'cost') else product.price,
                    "sellingPrice": product.selling_price if hasattr(product, 'selling_price') else None,
                    "unit": product.unit if hasattr(product, 'unit') else "건",
                    "minQuantity": product.min_quantity if hasattr(product, 'min_quantity') else 1,
                    "maxQuantity": product.max_quantity if hasattr(product, 'max_quantity') else None,
                    "sku": product.sku if hasattr(product, 'sku') else None,
                    "isActive": product.is_active,
                    "createdAt": product.created_at.isoformat() if product.created_at else None
                }

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
        # work_type 처리 - category name으로 work_type_id 찾기 (회사별 필터링)
        work_type_id = product_data.work_type_id
        user_company = current_user.company or 'default_company'

        if product_data.category and not work_type_id:
            work_type_query = select(WorkType).where(
                WorkType.name == product_data.category,
                WorkType.is_active == True,
                (WorkType.company == user_company) | (WorkType.company.is_(None))
            )
            result = await db.execute(work_type_query)
            work_type = result.scalars().first()  # scalar_one_or_none() 대신 first() 사용
            if work_type:
                work_type_id = work_type.id

        # SKU 중복 확인 (회사 내에서만)
        if product_data.sku:
            user_company = current_user.company or 'default_company'
            existing_sku_query = select(Product).where(
                Product.sku == product_data.sku,
                (Product.company == user_company) | (Product.company.is_(None))
            )
            result = await db.execute(existing_sku_query)
            existing_product = result.scalar_one_or_none()
            if existing_product:
                raise HTTPException(status_code=400, detail="이미 존재하는 SKU입니다")

        # 새 상품 생성 (모든 필드 저장)
        user_company = current_user.company or 'default_company'
        new_product = Product(
            name=product_data.name,
            description=product_data.description or "",
            price=product_data.costPrice,  # cost price를 price 필드에 저장
            cost=product_data.costPrice,   # 호환성을 위해 cost도 저장
            category=product_data.category,  # 기존 category 필드 사용
            sku=product_data.sku,
            selling_price=product_data.sellingPrice,  # 권장판매가 저장
            unit=product_data.unit,  # 단위 저장
            min_quantity=product_data.minQuantity,  # 최소수량 저장
            max_quantity=product_data.maxQuantity,  # 최대수량 저장
            is_active=True,
            company=user_company  # 회사별 데이터 분리
        )

        db.add(new_product)
        await db.commit()
        await db.refresh(new_product)

        print(f"[PRODUCT-CREATE] SUCCESS: Created product {new_product.id} by user {current_user.id}")

        return {
            "id": new_product.id,
            "name": new_product.name,
            "description": new_product.description,
            "category": new_product.category,
            "sku": new_product.sku,
            "costPrice": new_product.price,
            "sellingPrice": product_data.sellingPrice,  # 프론트엔드 호환성을 위해 포함
            "unit": product_data.unit,  # 프론트엔드 호환성을 위해 포함
            "minQuantity": product_data.minQuantity,  # 프론트엔드 호환성을 위해 포함
            "maxQuantity": product_data.maxQuantity,  # 프론트엔드 호환성을 위해 포함
            "tags": product_data.tags,  # 프론트엔드 호환성을 위해 포함
            "isActive": new_product.is_active,
            "createdAt": new_product.created_at.isoformat() if new_product.created_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PRODUCT-CREATE] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"상품 생성 중 오류: {str(e)}")


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: int,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """상품 삭제 (소프트 삭제)"""
    print(f"[PRODUCT-DELETE] Deleting product ID: {product_id}")

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

        print(f"[PRODUCT-DELETE] Node.js API mode - user_id={user_id}, role={user_role}")

    else:
        # JWT 기반 모드
        current_user = jwt_user
        user_role = current_user.role.value

        print(f"[PRODUCT-DELETE] JWT mode - user_id={current_user.id}, role={user_role}")

    try:
        # 상품 존재 확인 (회사별 필터링)
        product_query = select(Product).where(
            Product.id == product_id,
            (Product.company == (current_user.company or 'default_company')) | (Product.company.is_(None))
        )
        result = await db.execute(product_query)
        product = result.scalar_one_or_none()

        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")

        if not product.is_active:
            raise HTTPException(status_code=404, detail="이미 삭제된 상품입니다")

        # 소프트 삭제 (is_active를 False로 설정)
        product.is_active = False
        await db.commit()

        print(f"[PRODUCT-DELETE] SUCCESS: Soft deleted product {product_id} by user {current_user.id}")

        # 204 No Content 응답 (응답 바디 없음)
        return

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PRODUCT-DELETE] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"상품 삭제 중 오류: {str(e)}")


@router.put("/{product_id}", response_model=dict)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    # Node.js API 호환성을 위한 쿼리 파라미터
    viewerId: Optional[int] = Query(None, alias="viewerId"),
    adminId: Optional[int] = Query(None, alias="adminId"),
    viewerRole: Optional[str] = Query(None, alias="viewerRole"),
    adminRole: Optional[str] = Query(None, alias="adminRole"),
    db: AsyncSession = Depends(get_async_db),
    jwt_user: User = Depends(get_current_active_user)
):
    """상품 정보 수정"""
    print(f"[PRODUCT-UPDATE] Updating product ID: {product_id} with data: {product_data.dict(exclude_unset=True)}")

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

        print(f"[PRODUCT-UPDATE] Node.js API mode - user_id={user_id}, role={user_role}")

    else:
        # JWT 기반 모드
        current_user = jwt_user
        user_role = current_user.role.value

        print(f"[PRODUCT-UPDATE] JWT mode - user_id={current_user.id}, role={user_role}")

    try:
        # 상품 존재 확인 (회사별 필터링)
        product_query = select(Product).where(
            Product.id == product_id,
            (Product.company == (current_user.company or 'default_company')) | (Product.company.is_(None))
        )
        result = await db.execute(product_query)
        product = result.scalar_one_or_none()

        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")

        # is_active 변경 요청이 아닌 경우에만 삭제 상품 수정 차단
        if not product.is_active and product_data.isActive is None:
            raise HTTPException(status_code=404, detail="삭제된 상품은 수정할 수 없습니다")

        # SKU 중복 확인 (변경된 경우에만, 회사 내에서만)
        if product_data.sku and product_data.sku != product.sku:
            existing_sku_query = select(Product).where(
                Product.sku == product_data.sku,
                Product.id != product_id,
                (Product.company == (current_user.company or 'default_company')) | (Product.company.is_(None))
            )
            result = await db.execute(existing_sku_query)
            existing_product = result.scalar_one_or_none()
            if existing_product:
                raise HTTPException(status_code=400, detail="이미 존재하는 SKU입니다")

        # work_type 처리 - category name으로 work_type_id 찾기 (회사별 필터링)
        work_type_id = product_data.work_type_id
        if product_data.category and not work_type_id:
            user_company = current_user.company or 'default_company'
            work_type_query = select(WorkType).where(
                WorkType.name == product_data.category,
                WorkType.is_active == True,
                (WorkType.company == user_company) | (WorkType.company.is_(None))
            )
            result = await db.execute(work_type_query)
            work_type = result.scalars().first()  # scalar_one_or_none() 대신 first() 사용
            if work_type:
                work_type_id = work_type.id

        # 제공된 필드만 업데이트 (부분 업데이트)
        update_data = product_data.dict(exclude_unset=True)
        # camelCase → snake_case 매핑
        field_mapping = {
            "costPrice": None,  # 별도 처리
            "isActive": "is_active",
            "workTypeId": "work_type_id",
        }
        for field, value in update_data.items():
            if field == "costPrice":
                # costPrice를 price 필드와 cost 필드 모두에 저장
                product.price = value
                product.cost = value
            elif field in field_mapping and field_mapping[field]:
                setattr(product, field_mapping[field], value)
            elif hasattr(product, field):
                setattr(product, field, value)

        await db.commit()
        await db.refresh(product)

        print(f"[PRODUCT-UPDATE] SUCCESS: Updated product {product_id} by user {current_user.id}")

        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "category": product.category,
            "sku": product.sku,
            "costPrice": product.price,
            "sellingPrice": product_data.sellingPrice,  # 프론트엔드 호환성을 위해 포함
            "unit": product_data.unit or "건",  # 프론트엔드 호환성을 위해 포함
            "minQuantity": product_data.minQuantity or 1,  # 프론트엔드 호환성을 위해 포함
            "maxQuantity": product_data.maxQuantity,  # 프론트엔드 호환성을 위해 포함
            "tags": product_data.tags or "",  # 프론트엔드 호환성을 위해 포함
            "isActive": product.is_active,
            "createdAt": product.created_at.isoformat() if product.created_at else None,
            "updatedAt": product.updated_at.isoformat() if product.updated_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PRODUCT-UPDATE] Unexpected error: {type(e).__name__}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"상품 수정 중 오류: {str(e)}")