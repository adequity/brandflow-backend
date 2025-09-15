"""
관리자 전용 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_db
from app.db.cleanup_data import cleanup_dummy_data, reset_database_to_production
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole

router = APIRouter()


@router.post("/cleanup-dummy-data")
async def cleanup_dummy_data_endpoint(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """더미 데이터 정리 (슈퍼 어드민 전용)"""
    
    # 슈퍼 어드민 권한 확인
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="슈퍼 어드민만 더미 데이터를 정리할 수 있습니다."
        )
    
    try:
        await cleanup_dummy_data(db)
        return {
            "message": "더미 데이터가 성공적으로 정리되었습니다.",
            "details": "슈퍼 어드민 계정만 남겨두고 모든 테스트 데이터가 삭제되었습니다."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"더미 데이터 정리 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/reset-to-production")
async def reset_to_production_endpoint(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """프로덕션 환경으로 데이터베이스 초기화 (슈퍼 어드민 전용)"""
    
    # 슈퍼 어드민 권한 확인
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="슈퍼 어드민만 프로덕션 초기화를 실행할 수 있습니다."
        )
    
    try:
        await reset_database_to_production(db)
        return {
            "message": "데이터베이스가 프로덕션 환경으로 성공적으로 초기화되었습니다.",
            "details": "슈퍼 어드민 계정만 존재하며, 모든 더미 데이터는 제거되었습니다."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"프로덕션 초기화 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/system-status")
async def get_system_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """시스템 상태 조회 (슈퍼 어드민 전용)"""
    
    # 슈퍼 어드민 권한 확인
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="슈퍼 어드민만 시스템 상태를 조회할 수 있습니다."
        )
    
    try:
        from sqlalchemy import select, func
        from app.models.user import User
        from app.models.campaign import Campaign
        from app.models.purchase_request import PurchaseRequest
        
        # 각 테이블의 데이터 수 조회
        user_count = await db.scalar(select(func.count(User.id)))
        campaign_count = await db.scalar(select(func.count(Campaign.id)))
        purchase_request_count = await db.scalar(select(func.count(PurchaseRequest.id)))
        
        # 슈퍼 어드민 수 조회
        superuser_count = await db.scalar(
            select(func.count(User.id)).where(User.role == UserRole.SUPER_ADMIN)
        )
        
        return {
            "system_status": "운영중",
            "database_counts": {
                "users": user_count,
                "superusers": superuser_count,
                "campaigns": campaign_count,
                "purchase_requests": purchase_request_count
            },
            "is_production_ready": user_count == superuser_count and campaign_count == 0 and purchase_request_count == 0
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시스템 상태 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/migrate-database")
async def migrate_database_endpoint(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """데이터베이스 스키마 마이그레이션 실행 (슈퍼 어드민 전용)"""
    
    # 슈퍼 어드민 권한 확인
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="슈퍼 어드민만 데이터베이스 마이그레이션을 실행할 수 있습니다."
        )
    
    try:
        from sqlalchemy import text
        from app.db.database import add_client_user_id_column, migrate_client_company_to_user_id
        
        # 1. client_user_id 컬럼 추가
        await add_client_user_id_column()
        
        # 2. 기존 데이터 마이그레이션
        await migrate_client_company_to_user_id()
        
        # 3. 마이그레이션 결과 확인
        check_result = await db.execute(text("""
            SELECT COUNT(*) as total_campaigns,
                   COUNT(client_user_id) as with_client_user_id,
                   COUNT(CASE WHEN client_company LIKE '%(ID: %)' THEN 1 END) as with_id_pattern
            FROM campaigns
        """))
        stats = check_result.fetchone()
        
        return {
            "message": "데이터베이스 마이그레이션이 성공적으로 완료되었습니다.",
            "details": {
                "client_user_id_column_added": True,
                "data_migration_completed": True,
                "migration_stats": {
                    "total_campaigns": stats[0],
                    "campaigns_with_client_user_id": stats[1],
                    "campaigns_with_id_pattern": stats[2]
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"데이터베이스 마이그레이션 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/schema-status")
async def get_schema_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """데이터베이스 스키마 상태 확인 (슈퍼 어드민 전용)"""
    
    # 슈퍼 어드민 권한 확인
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="슈퍼 어드민만 스키마 상태를 조회할 수 있습니다."
        )
    
    try:
        from sqlalchemy import text
        
        # 1. client_user_id 컬럼 존재 여부 확인
        column_result = await db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'campaigns' AND column_name = 'client_user_id'
        """))
        client_user_id_exists = column_result.fetchone() is not None
        
        # 2. campaigns 테이블 통계
        stats_result = await db.execute(text("""
            SELECT COUNT(*) as total_campaigns,
                   COUNT(CASE WHEN client_company LIKE '%(ID: %)' THEN 1 END) as with_id_pattern
            FROM campaigns
        """))
        stats = stats_result.fetchone()
        
        # 3. client_user_id가 있는 경우 추가 통계
        client_user_id_stats = None
        if client_user_id_exists:
            client_stats_result = await db.execute(text("""
                SELECT COUNT(client_user_id) as with_client_user_id
                FROM campaigns
                WHERE client_user_id IS NOT NULL
            """))
            client_user_id_stats = client_stats_result.fetchone()[0]
        
        return {
            "schema_status": {
                "client_user_id_column_exists": client_user_id_exists,
                "migration_needed": not client_user_id_exists or (client_user_id_stats == 0 and stats[1] > 0)
            },
            "campaign_statistics": {
                "total_campaigns": stats[0],
                "campaigns_with_id_pattern": stats[1],
                "campaigns_with_client_user_id": client_user_id_stats if client_user_id_exists else 0
            },
            "recommendations": {
                "run_migration": not client_user_id_exists or (client_user_id_stats == 0 and stats[1] > 0)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"스키마 상태 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/smart-migration")
async def smart_migration_endpoint(
    dry_run: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """스마트 데이터 마이그레이션 실행 (슈퍼 어드민 전용)"""
    
    # 슈퍼 어드민 권한 확인
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="슈퍼 어드민만 스마트 마이그레이션을 실행할 수 있습니다."
        )
    
    try:
        from app.db.smart_migration import SmartDataMigrator
        
        migrator = SmartDataMigrator()
        stats = await migrator.execute_smart_migration(db, dry_run=dry_run)
        
        return {
            "message": f"스마트 마이그레이션이 {'분석' if dry_run else '완료'}되었습니다.",
            "dry_run": dry_run,
            "statistics": {
                "total_unmapped_campaigns": stats['total_unmapped'],
                "id_pattern_matches": stats['id_pattern_matches'],
                "name_matches": stats['name_matches'], 
                "email_matches": stats['email_matches'],
                "company_matches": stats['company_matches'],
                "no_matches": stats['no_matches'],
                "successfully_updated": stats.get('updated', 0)
            },
            "recommendations": {
                "potential_matches": stats['total_unmapped'] - stats['no_matches'],
                "success_rate": round((stats['total_unmapped'] - stats['no_matches']) / max(stats['total_unmapped'], 1) * 100, 1) if stats['total_unmapped'] > 0 else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"스마트 마이그레이션 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/migration-analysis")
async def migration_analysis_endpoint(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """마이그레이션 분석 결과 조회 (슈퍼 어드민 전용)"""
    
    # 슈퍼 어드민 권한 확인
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="슈퍼 어드민만 마이그레이션 분석을 조회할 수 있습니다."
        )
    
    try:
        from app.db.smart_migration import SmartDataMigrator
        
        migrator = SmartDataMigrator()
        await migrator.load_user_cache(db)
        
        unmapped_campaigns = await migrator.analyze_unmapped_campaigns(db)
        
        # 분석 결과 정리
        analysis_results = []
        match_type_counts = {
            'ID_PATTERN': 0,
            'NAME_MATCH': 0, 
            'EMAIL_MATCH': 0,
            'COMPANY_MATCH': 0,
            'NO_MATCH': 0
        }
        
        for campaign in unmapped_campaigns[:20]:  # 최대 20개만 반환
            patterns = campaign['extracted_patterns']
            suggested_user_id = campaign['suggested_user_id']
            
            if 'user_id' in patterns and suggested_user_id == patterns['user_id']:
                match_type = "ID_PATTERN"
            elif suggested_user_id:
                user_info = migrator.user_cache.get(suggested_user_id, {})
                if 'name' in patterns and migrator.normalize_text(patterns['name']) == user_info.get('normalized_name', ''):
                    match_type = "NAME_MATCH"
                elif 'email' in patterns and patterns['email'].lower() == user_info.get('email', '').lower():
                    match_type = "EMAIL_MATCH"
                else:
                    match_type = "COMPANY_MATCH"
            else:
                match_type = "NO_MATCH"
            
            match_type_counts[match_type] += 1
            
            analysis_results.append({
                "campaign_id": campaign['id'],
                "campaign_name": campaign['name'],
                "client_company": campaign['client_company'],
                "extracted_patterns": patterns,
                "suggested_user_id": suggested_user_id,
                "suggested_user_name": campaign['suggested_user_name'],
                "match_type": match_type,
                "confidence": "HIGH" if match_type == "ID_PATTERN" else "MEDIUM" if suggested_user_id else "LOW"
            })
        
        return {
            "total_unmapped": len(unmapped_campaigns),
            "showing_count": min(len(unmapped_campaigns), 20),
            "match_type_summary": match_type_counts,
            "analysis_results": analysis_results,
            "recommendations": {
                "ready_for_migration": len(unmapped_campaigns) - match_type_counts['NO_MATCH'],
                "requires_manual_review": match_type_counts['NO_MATCH']
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"마이그레이션 분석 중 오류가 발생했습니다: {str(e)}"
        )