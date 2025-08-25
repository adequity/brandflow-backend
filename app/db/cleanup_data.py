"""
더미 데이터 정리를 위한 모듈
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.user import User, UserRole
from app.models.campaign import Campaign
from app.models.purchase_request import PurchaseRequest


async def cleanup_dummy_data(db: AsyncSession):
    """더미/테스트 데이터 완전 정리"""
    print("더미 데이터 정리 중...")
    
    try:
        # 1. 구매요청 모두 삭제
        purchase_requests_result = await db.execute(select(PurchaseRequest))
        purchase_requests = purchase_requests_result.scalars().all()
        
        for pr in purchase_requests:
            await db.delete(pr)
        
        print(f"구매요청 {len(purchase_requests)}개 삭제됨")
        
        # 2. 캠페인 모두 삭제
        campaigns_result = await db.execute(select(Campaign))
        campaigns = campaigns_result.scalars().all()
        
        for campaign in campaigns:
            await db.delete(campaign)
        
        print(f"캠페인 {len(campaigns)}개 삭제됨")
        
        # 3. 슈퍼 어드민이 아닌 모든 사용자 삭제
        non_superuser_result = await db.execute(
            select(User).where(User.role != UserRole.SUPER_ADMIN)
        )
        non_superusers = non_superuser_result.scalars().all()
        
        for user in non_superusers:
            await db.delete(user)
        
        print(f"슈퍼 어드민이 아닌 사용자 {len(non_superusers)}개 삭제됨")
        
        # 커밋
        await db.commit()
        
        print("\n=== 더미 데이터 정리 완료 ===")
        print("슈퍼 어드민 계정만 남겨두고 모든 더미 데이터가 삭제되었습니다.")
        print("=============================")
        
        return True
        
    except Exception as e:
        print(f"더미 데이터 정리 중 오류 발생: {str(e)}")
        await db.rollback()
        raise


async def reset_database_to_production(db: AsyncSession):
    """데이터베이스를 프로덕션 상태로 초기화"""
    print("데이터베이스를 프로덕션 상태로 초기화 중...")
    
    try:
        # 1. 더미 데이터 정리
        await cleanup_dummy_data(db)
        
        # 2. 슈퍼 어드민 계정 확인/생성
        from app.db.init_data import create_superuser
        await create_superuser(db)
        
        await db.commit()
        
        print("\n=== 프로덕션 초기화 완료 ===")
        print("데이터베이스가 프로덕션 환경으로 초기화되었습니다.")
        print("슈퍼 어드민 계정만 존재하며, 모든 더미 데이터는 제거되었습니다.")
        print("==============================")
        
    except Exception as e:
        print(f"프로덕션 초기화 중 오류 발생: {str(e)}")
        await db.rollback()
        raise