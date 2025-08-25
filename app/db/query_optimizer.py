"""
데이터베이스 쿼리 최적화 도구
- 느린 쿼리 감지 및 개선
- 인덱스 추천 시스템
- 쿼리 캐싱 전략
- N+1 문제 해결
"""

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Dict, Optional
import asyncio
from datetime import datetime

from app.models.user import User
from app.models.campaign import Campaign
from app.models.purchase_request import PurchaseRequest

class QueryOptimizer:
    def __init__(self):
        self.query_cache = {}
        self.cache_ttl = 300  # 5분 캐시
    
    async def get_campaigns_with_users_optimized(self, db: AsyncSession, company: str = None) -> List[Campaign]:
        """캠페인+사용자 정보를 효율적으로 조회 (N+1 문제 해결)"""
        query = select(Campaign).options(
            joinedload(Campaign.creator)  # 한 번의 쿼리로 사용자 정보까지 가져오기
        )
        
        if company:
            query = query.join(User, Campaign.creator_id == User.id).where(User.company == company)
        
        result = await db.execute(query)
        return result.unique().scalars().all()
    
    async def get_user_with_campaigns_optimized(self, db: AsyncSession, user_id: int) -> Optional[User]:
        """사용자+캠페인 정보를 효율적으로 조회"""
        query = select(User).options(
            selectinload(User.campaigns)  # 별도 쿼리로 캠페인 정보 미리 로드
        ).where(User.id == user_id)
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_dashboard_data_optimized(self, db: AsyncSession, user_id: int, user_role: str) -> Dict:
        """대시보드 데이터를 최적화된 쿼리로 조회"""
        cache_key = f"dashboard_{user_id}_{user_role}"
        
        # 캐시 확인
        if cache_key in self.query_cache:
            cached_data, timestamp = self.query_cache[cache_key]
            if (datetime.now() - timestamp).seconds < self.cache_ttl:
                return cached_data
        
        # 병렬로 여러 쿼리 실행
        tasks = []
        
        # 1. 캠페인 통계
        campaigns_task = self._get_campaign_stats(db, user_id, user_role)
        tasks.append(campaigns_task)
        
        # 2. 구매요청 통계  
        purchase_requests_task = self._get_purchase_request_stats(db, user_id, user_role)
        tasks.append(purchase_requests_task)
        
        # 3. 사용자별 데이터
        user_data_task = self._get_user_data(db, user_id)
        tasks.append(user_data_task)
        
        # 모든 쿼리 병렬 실행
        campaign_stats, purchase_stats, user_data = await asyncio.gather(*tasks)
        
        dashboard_data = {
            'campaigns': campaign_stats,
            'purchase_requests': purchase_stats,
            'user': user_data,
            'generated_at': datetime.now().isoformat()
        }
        
        # 캐시 저장
        self.query_cache[cache_key] = (dashboard_data, datetime.now())
        
        return dashboard_data
    
    async def _get_campaign_stats(self, db: AsyncSession, user_id: int, user_role: str) -> Dict:
        """캠페인 통계 조회 (최적화된 집계 쿼리)"""
        base_query = select(
            Campaign.status,
            func.count(Campaign.id).label('count'),
            func.coalesce(func.sum(Campaign.budget), 0).label('total_budget')
        ).group_by(Campaign.status)
        
        # 권한별 필터링
        if user_role == '클라이언트':
            base_query = base_query.where(Campaign.creator_id == user_id)
        elif user_role in ['대행사 어드민', '직원']:
            # 같은 회사 사용자들의 캠페인만
            user_subquery = select(User.id).where(
                User.company == select(User.company).where(User.id == user_id).scalar_subquery()
            )
            base_query = base_query.where(Campaign.creator_id.in_(user_subquery))
        
        result = await db.execute(base_query)
        rows = result.fetchall()
        
        stats = {}
        for row in rows:
            stats[row.status] = {
                'count': row.count,
                'total_budget': float(row.total_budget)
            }
        
        return stats
    
    async def _get_purchase_request_stats(self, db: AsyncSession, user_id: int, user_role: str) -> Dict:
        """구매요청 통계 조회"""
        from sqlalchemy import func
        
        base_query = select(
            PurchaseRequest.status,
            func.count(PurchaseRequest.id).label('count'),
            func.coalesce(func.sum(PurchaseRequest.amount), 0).label('total_amount')
        ).group_by(PurchaseRequest.status)
        
        # 권한별 필터링 (캠페인과 동일한 로직)
        if user_role == '클라이언트':
            base_query = base_query.where(PurchaseRequest.requester_id == user_id)
        elif user_role in ['대행사 어드민', '직원']:
            user_subquery = select(User.id).where(
                User.company == select(User.company).where(User.id == user_id).scalar_subquery()
            )
            base_query = base_query.where(PurchaseRequest.requester_id.in_(user_subquery))
        
        result = await db.execute(base_query)
        rows = result.fetchall()
        
        stats = {}
        for row in rows:
            stats[row.status] = {
                'count': row.count,
                'total_amount': float(row.total_amount) if row.total_amount else 0
            }
        
        return stats
    
    async def _get_user_data(self, db: AsyncSession, user_id: int) -> Dict:
        """사용자 기본 정보 조회"""
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return {}
        
        return {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'company': user.company,
            'role': user.role.value if hasattr(user.role, 'value') else user.role
        }
    
    def clear_cache(self, pattern: str = None):
        """캐시 정리"""
        if pattern:
            keys_to_remove = [key for key in self.query_cache.keys() if pattern in key]
            for key in keys_to_remove:
                del self.query_cache[key]
        else:
            self.query_cache.clear()
    
    async def analyze_slow_queries(self, db: AsyncSession) -> List[Dict]:
        """느린 쿼리 분석 및 개선 제안"""
        slow_queries = []
        
        # 복잡한 JOIN 쿼리 테스트
        test_queries = [
            {
                'name': 'campaigns_with_users',
                'query': '''
                    SELECT c.*, u.name as creator_name, u.company 
                    FROM campaigns c 
                    LEFT JOIN users u ON c.creator_id = u.id
                ''',
                'suggestion': '캠페인 조회 시 joinedload() 사용 권장'
            },
            {
                'name': 'user_campaign_stats',
                'query': '''
                    SELECT u.name, COUNT(c.id) as campaign_count, SUM(c.budget) as total_budget
                    FROM users u 
                    LEFT JOIN campaigns c ON u.id = c.creator_id 
                    GROUP BY u.id, u.name
                ''',
                'suggestion': 'selectinload()를 사용하여 N+1 문제 방지'
            }
        ]
        
        for test in test_queries:
            start_time = datetime.now()
            try:
                await db.execute(text(test['query']))
                duration = (datetime.now() - start_time).total_seconds()
                
                if duration > 0.1:  # 100ms 이상
                    slow_queries.append({
                        'name': test['name'],
                        'duration': round(duration, 3),
                        'query': test['query'],
                        'suggestion': test['suggestion']
                    })
            except Exception as e:
                slow_queries.append({
                    'name': test['name'],
                    'error': str(e),
                    'suggestion': test['suggestion']
                })
        
        return slow_queries

# 전역 쿼리 최적화 인스턴스
query_optimizer = QueryOptimizer()