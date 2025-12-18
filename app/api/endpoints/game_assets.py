"""
게임 에셋 API 엔드포인트
- 공개 API: 게임에서 에셋 조회
- 관리자 API: 에셋 CRUD
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.models.game_asset import GameAsset

router = APIRouter()


# Pydantic Schemas
class GameAssetBase(BaseModel):
    name: str
    category: str = "기타"
    game_type: str
    image_url: Optional[str] = None


class GameAssetCreate(GameAssetBase):
    pass


class GameAssetUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    game_type: Optional[str] = None
    image_url: Optional[str] = None


class GameAssetResponse(GameAssetBase):
    id: int
    usage_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class GameAssetListResponse(BaseModel):
    assets: List[GameAssetResponse]
    total: int


# =====================
# 공개 API (인증 불필요)
# =====================

@router.get("/assets", response_model=GameAssetListResponse, tags=["Game Public"])
async def get_game_assets(
    game_type: str = Query(..., description="게임 타입 (같은그림찾기, 기억력게임, 틀린그림찾기)"),
    limit: int = Query(16, ge=1, le=50, description="조회 개수"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    게임 타입별 에셋 목록 조회 (공개 API)
    게임에서 사용할 에셋 이미지를 조회합니다.
    """
    try:
        result = await db.execute(
            select(GameAsset)
            .where(GameAsset.game_type == game_type)
            .where(GameAsset.image_url.isnot(None))
            .where(GameAsset.image_url != "")
            .order_by(GameAsset.created_at.desc())
            .limit(limit)
        )
        assets = result.scalars().all()

        return GameAssetListResponse(
            assets=[GameAssetResponse.model_validate(asset) for asset in assets],
            total=len(assets)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"에셋 조회 실패: {str(e)}")


@router.post("/assets/usage", tags=["Game Public"])
async def increment_asset_usage(
    asset_ids: List[int],
    db: AsyncSession = Depends(get_async_db)
):
    """
    에셋 사용 횟수 증가 (통계용)
    """
    try:
        await db.execute(
            update(GameAsset)
            .where(GameAsset.id.in_(asset_ids))
            .values(usage_count=GameAsset.usage_count + 1)
        )
        await db.commit()
        return {"message": "사용 횟수가 업데이트되었습니다."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"사용 횟수 업데이트 실패: {str(e)}")


# =====================
# 관리자 API (인증 필요)
# =====================

@router.get("/superadmin/assets", response_model=List[GameAssetResponse], tags=["SuperAdmin"])
async def list_all_assets(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    모든 에셋 목록 조회 (슈퍼 어드민 전용)
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="슈퍼 어드민만 접근할 수 있습니다.")

    result = await db.execute(
        select(GameAsset).order_by(GameAsset.created_at.desc())
    )
    assets = result.scalars().all()
    return [GameAssetResponse.model_validate(asset) for asset in assets]


@router.post("/superadmin/assets", response_model=GameAssetResponse, tags=["SuperAdmin"])
async def create_asset(
    asset_data: GameAssetCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    새 에셋 생성 (슈퍼 어드민 전용)
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="슈퍼 어드민만 접근할 수 있습니다.")

    try:
        new_asset = GameAsset(
            name=asset_data.name,
            category=asset_data.category,
            game_type=asset_data.game_type,
            image_url=asset_data.image_url
        )
        db.add(new_asset)
        await db.commit()
        await db.refresh(new_asset)
        return GameAssetResponse.model_validate(new_asset)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"에셋 생성 실패: {str(e)}")


@router.put("/superadmin/assets/{asset_id}", response_model=GameAssetResponse, tags=["SuperAdmin"])
async def update_asset(
    asset_id: int,
    asset_data: GameAssetUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    에셋 수정 (슈퍼 어드민 전용)
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="슈퍼 어드민만 접근할 수 있습니다.")

    result = await db.execute(
        select(GameAsset).where(GameAsset.id == asset_id)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="에셋을 찾을 수 없습니다.")

    try:
        update_data = asset_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(asset, key, value)

        await db.commit()
        await db.refresh(asset)
        return GameAssetResponse.model_validate(asset)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"에셋 수정 실패: {str(e)}")


@router.delete("/superadmin/assets/{asset_id}", tags=["SuperAdmin"])
async def delete_asset(
    asset_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    에셋 삭제 (슈퍼 어드민 전용)
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="슈퍼 어드민만 접근할 수 있습니다.")

    result = await db.execute(
        select(GameAsset).where(GameAsset.id == asset_id)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="에셋을 찾을 수 없습니다.")

    try:
        await db.delete(asset)
        await db.commit()
        return {"message": "에셋이 삭제되었습니다."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"에셋 삭제 실패: {str(e)}")
