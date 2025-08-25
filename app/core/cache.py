"""
Simple in-memory cache for BrandFlow API
"""

import time
from typing import Any, Optional, Dict, Tuple
import asyncio
from functools import wraps
import json
import hashlib


class SimpleCache:
    """간단한 인메모리 캐시"""
    
    def __init__(self, default_ttl: int = 300):  # 5분 기본 TTL
        self.cache: Dict[str, Tuple[Any, float]] = {}  # key: (value, expiry_time)
        self.default_ttl = default_ttl
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        async with self._lock:
            if key in self.cache:
                value, expiry_time = self.cache[key]
                if time.time() < expiry_time:
                    return value
                else:
                    # 만료된 항목 삭제
                    del self.cache[key]
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """캐시에 값 설정"""
        async with self._lock:
            ttl = ttl or self.default_ttl
            expiry_time = time.time() + ttl
            self.cache[key] = (value, expiry_time)
    
    async def delete(self, key: str) -> bool:
        """캐시에서 항목 삭제"""
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """모든 캐시 삭제"""
        async with self._lock:
            self.cache.clear()
    
    async def cleanup_expired(self) -> int:
        """만료된 항목 정리"""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, expiry_time) in self.cache.items()
                if current_time >= expiry_time
            ]
            for key in expired_keys:
                del self.cache[key]
            return len(expired_keys)
    
    def get_stats(self) -> dict:
        """캐시 통계"""
        current_time = time.time()
        total_items = len(self.cache)
        expired_items = sum(
            1 for _, expiry_time in self.cache.values()
            if current_time >= expiry_time
        )
        active_items = total_items - expired_items
        
        return {
            "total_items": total_items,
            "active_items": active_items,
            "expired_items": expired_items,
            "memory_usage_estimate": len(str(self.cache))  # 대략적인 메모리 사용량
        }


# 전역 캐시 인스턴스
app_cache = SimpleCache(default_ttl=60)  # 1분 기본 TTL


def cache_key(*args, **kwargs) -> str:
    """캐시 키 생성 (User 객체 호환)"""
    def serialize_value(value):
        """값을 직렬화 가능한 형태로 변환"""
        if hasattr(value, '__dict__') and hasattr(value, '__class__'):
            # SQLAlchemy 모델이나 클래스 인스턴스인 경우
            if hasattr(value, 'id'):
                # User 객체 등 ID가 있는 경우 ID 사용
                return f"{value.__class__.__name__}_{value.id}"
            elif hasattr(value, 'email'):
                # 이메일이 있는 경우 이메일 사용
                return f"{value.__class__.__name__}_{value.email}"
            else:
                # 기타 객체는 클래스명만 사용
                return f"{value.__class__.__name__}_{hash(str(value))}"
        return value
    
    # 함수 인자들을 직렬화 가능한 형태로 변환
    serializable_args = [serialize_value(arg) for arg in args]
    serializable_kwargs = {k: serialize_value(v) for k, v in kwargs.items()}
    
    key_data = {"args": serializable_args, "kwargs": serializable_kwargs}
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(ttl: int = 60, key_prefix: str = ""):
    """캐시 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 캐시 키 생성
            func_key = f"{key_prefix}{func.__name__}"
            cache_key_hash = cache_key(*args, **kwargs)
            full_key = f"{func_key}:{cache_key_hash}"
            
            # 캐시에서 조회
            cached_result = await app_cache.get(full_key)
            if cached_result is not None:
                return cached_result
            
            # 캐시 미스 - 함수 실행
            result = await func(*args, **kwargs)
            
            # 결과 캐싱
            await app_cache.set(full_key, result, ttl)
            
            return result
        return wrapper
    return decorator


# 사용자별 캐시 무효화를 위한 헬퍼 함수
async def invalidate_user_cache(user_id: int):
    """특정 사용자의 캐시 무효화"""
    # 사용자 관련 캐시 키 패턴들
    patterns = [
        f"unread_count_user_{user_id}",
        f"user_notifications_{user_id}",
        f"user_dashboard_{user_id}",
    ]
    
    for pattern in patterns:
        await app_cache.delete(pattern)


async def invalidate_global_cache():
    """전역 캐시 무효화 (드물게 사용)"""
    await app_cache.clear()


# 백그라운드 정리 태스크
async def cache_cleanup_task():
    """주기적으로 만료된 캐시 정리"""
    while True:
        try:
            cleaned = await app_cache.cleanup_expired()
            if cleaned > 0:
                print(f"Cache cleanup: removed {cleaned} expired items")
            await asyncio.sleep(300)  # 5분마다 정리
        except Exception as e:
            print(f"Cache cleanup error: {e}")
            await asyncio.sleep(60)  # 에러 시 1분 후 재시도