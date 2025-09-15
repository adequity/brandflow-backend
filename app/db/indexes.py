"""
Database index optimization for BrandFlow API
Optimizes common query patterns found in the application
"""

from sqlalchemy import Index
from app.models.user import User
from app.models.campaign import Campaign
from app.models.purchase_request import PurchaseRequest

# 성능 최적화를 위한 인덱스 정의

# User 테이블 인덱스
user_indexes = [
    # 기존: id (PK), email (unique) 인덱스는 이미 존재
    
    # 1. 회사별 사용자 조회 최적화 (대행사 어드민 권한 체크용)
    Index('ix_users_company', User.company),
    
    # 2. 활성 사용자 필터링 최적화
    Index('ix_users_status_active', User.status, User.is_active),
    
    # 3. 역할별 사용자 조회 최적화
    Index('ix_users_role', User.role),
    
    # 4. 복합 인덱스: 회사별 + 활성 상태 (가장 많이 사용되는 조합)
    Index('ix_users_company_status', User.company, User.status, User.is_active),
]

# Campaign 테이블 인덱스
campaign_indexes = [
    # 기존: id (PK) 인덱스는 이미 존재
    
    # 1. 생성자별 캠페인 조회 최적화 (creator_id 외래키)
    Index('ix_campaigns_creator_id', Campaign.creator_id),
    
    # 2. 상태별 캠페인 필터링 최적화 (active 캠페인 조회)
    Index('ix_campaigns_status', Campaign.status),
    
    # 3. 날짜 범위 조회 최적화
    Index('ix_campaigns_dates', Campaign.start_date, Campaign.end_date),
    
    # 4. 클라이언트 회사별 캠페인 조회 최적화
    Index('ix_campaigns_client_company', Campaign.client_company),
    
    # 5. 복합 인덱스: 생성자 + 상태 (개별 사용자의 활성 캠페인 조회용)
    Index('ix_campaigns_creator_status', Campaign.creator_id, Campaign.status),
    
    # 6. 복합 인덱스: 상태 + 날짜 (활성 캠페인의 기간별 조회)
    Index('ix_campaigns_status_dates', Campaign.status, Campaign.start_date, Campaign.end_date),
]

# PurchaseRequest 테이블 인덱스
purchase_request_indexes = [
    # 기존: id (PK) 인덱스는 이미 존재
    
    # 1. 요청자별 구매요청 조회 최적화
    Index('ix_purchase_requests_requester_id', PurchaseRequest.requester_id),
    
    # 2. 캠페인별 구매요청 조회 최적화
    Index('ix_purchase_requests_campaign_id', PurchaseRequest.campaign_id),
    
    # 3. 상태별 구매요청 필터링 최적화
    Index('ix_purchase_requests_status', PurchaseRequest.status),
    
    # 4. 공급업체별 조회 최적화
    Index('ix_purchase_requests_vendor', PurchaseRequest.vendor),
    
    # 5. 복합 인덱스: 요청자 + 상태 (사용자별 대기중인 요청 조회)
    Index('ix_purchase_requests_requester_status', PurchaseRequest.requester_id, PurchaseRequest.status),
    
    # 6. 복합 인덱스: 캠페인 + 상태 (캠페인별 승인된 구매요청 조회)
    Index('ix_purchase_requests_campaign_status', PurchaseRequest.campaign_id, PurchaseRequest.status),
]

# 모든 인덱스를 하나의 리스트로 수집
all_indexes = user_indexes + campaign_indexes + purchase_request_indexes

# 인덱스 생성 함수
async def create_performance_indexes(engine):
    """성능 최적화 인덱스를 생성합니다."""
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        # PostgreSQL CREATE INDEX IF NOT EXISTS로 안전하게 생성
        
        # User 테이블 인덱스
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_users_company 
            ON users (company)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_users_status_active 
            ON users (status, is_active)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_users_role 
            ON users (role)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_users_company_status 
            ON users (company, status, is_active)
        """))
        
        # Campaign 테이블 인덱스
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_campaigns_creator_id 
            ON campaigns (creator_id)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_campaigns_status 
            ON campaigns (status)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_campaigns_dates 
            ON campaigns (start_date, end_date)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_campaigns_client_company 
            ON campaigns (client_company)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_campaigns_creator_status 
            ON campaigns (creator_id, status)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_campaigns_status_dates 
            ON campaigns (status, start_date, end_date)
        """))
        
        # PurchaseRequest 테이블 인덱스
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_purchase_requests_requester_id 
            ON purchase_requests (requester_id)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_purchase_requests_campaign_id 
            ON purchase_requests (campaign_id)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_purchase_requests_status 
            ON purchase_requests (status)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_purchase_requests_vendor 
            ON purchase_requests (vendor)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_purchase_requests_requester_status 
            ON purchase_requests (requester_id, status)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_purchase_requests_campaign_status 
            ON purchase_requests (campaign_id, status)
        """))

    print("Performance indexes created successfully")

# 인덱스 사용량 분석 함수
async def analyze_index_usage(engine):
    """인덱스 사용량을 분석하고 리포트를 생성합니다."""
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        # PostgreSQL에서 인덱스 목록 조회
        result = await conn.execute(text("""
            SELECT indexname as name, tablename as tbl_name, indexdef as sql
            FROM pg_indexes 
            WHERE schemaname = 'public'
            AND indexname LIKE 'ix_%'
            ORDER BY tablename, indexname
        """))
        
        indexes = result.fetchall()
        
        print("Database Index Analysis")
        print("=" * 50)
        
        for idx in indexes:
            print(f"• {idx.name} on {idx.tbl_name}")
        
        print(f"\n총 커스텀 인덱스: {len(indexes)}개")
        return indexes

# 쿼리 성능 분석 함수
async def explain_query_performance(engine, query_sql: str):
    """쿼리의 실행 계획을 분석합니다."""
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        # PostgreSQL EXPLAIN
        result = await conn.execute(text(f"EXPLAIN ANALYZE {query_sql}"))
        plan = result.fetchall()
        
        print("Query Performance Analysis")
        print("=" * 50)
        print(f"Query: {query_sql}")
        print("\nExecution Plan:")
        
        for step in plan:
            print(f"  {step}")
        
        return plan