"""
Cache management API endpoints
"""

from fastapi import APIRouter
from app.core.cache import app_cache, invalidate_user_cache, invalidate_global_cache

router = APIRouter()


@router.get("/stats")
async def get_cache_stats():
    """캐시 통계 조회"""
    stats = app_cache.get_stats()
    return {
        "cache_stats": stats,
        "cache_type": "in_memory",
        "default_ttl_seconds": app_cache.default_ttl
    }


@router.post("/cleanup")
async def cleanup_expired_cache():
    """만료된 캐시 항목 정리"""
    cleaned_count = await app_cache.cleanup_expired()
    return {
        "message": f"Cleaned up {cleaned_count} expired cache items",
        "cleaned_items": cleaned_count
    }


@router.delete("/user/{user_id}")
async def invalidate_user_cache_endpoint(user_id: int):
    """특정 사용자의 캐시 무효화"""
    await invalidate_user_cache(user_id)
    return {
        "message": f"Cache invalidated for user {user_id}",
        "user_id": user_id
    }


@router.delete("/all")
async def clear_all_cache():
    """모든 캐시 삭제 (주의!)"""
    await invalidate_global_cache()
    return {
        "message": "All cache cleared",
        "warning": "This operation cleared all cached data"
    }


@router.get("/health")
async def cache_health_check():
    """캐시 시스템 헬스 체크"""
    stats = app_cache.get_stats()
    
    # 캐시 건강도 평가
    if stats["total_items"] > 1000:
        status = "warning"
        message = "High cache usage detected"
    elif stats["expired_items"] > stats["active_items"]:
        status = "degraded"
        message = "Too many expired items, cleanup recommended"
    else:
        status = "healthy"
        message = "Cache system operating normally"
    
    return {
        "status": status,
        "message": message,
        "cache_stats": stats
    }