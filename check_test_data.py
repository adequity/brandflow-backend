#!/usr/bin/env python3
"""
Test Data Verification Script
테스트 데이터 확인 스크립트
"""

import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.campaign import Campaign, CampaignStatus  
from app.models.purchase_request import PurchaseRequest, RequestStatus


async def check_test_data():
    """데이터베이스 테스트 데이터 확인"""
    print("=== 테스트 데이터 확인 ===")
    
    async with AsyncSessionLocal() as db:
        # 사용자 통계
        total_users = await db.scalar(select(func.count(User.id)))
        super_admins = await db.scalar(
            select(func.count(User.id)).where(User.role == UserRole.SUPER_ADMIN)
        )
        agency_admins = await db.scalar(
            select(func.count(User.id)).where(User.role == UserRole.AGENCY_ADMIN)
        )
        staff_users = await db.scalar(
            select(func.count(User.id)).where(User.role == UserRole.STAFF)
        )
        clients = await db.scalar(
            select(func.count(User.id)).where(User.role == UserRole.CLIENT)
        )
        
        print(f"\n[사용자 통계]")
        print(f"   전체 사용자: {total_users}명")
        print(f"   슈퍼 어드민: {super_admins}명")
        print(f"   대행사 어드민: {agency_admins}명") 
        print(f"   직원: {staff_users}명")
        print(f"   클라이언트: {clients}명")
        
        # 사용자 목록
        users = await db.execute(select(User).order_by(User.id))
        users = users.scalars().all()
        
        print(f"\n[사용자 목록]")
        for user in users:
            print(f"   {user.id}. {user.name} ({user.email}) - {user.role} - {user.company or 'N/A'}")
        
        # 캠페인 통계
        total_campaigns = await db.scalar(select(func.count(Campaign.id)))
        active_campaigns = await db.scalar(
            select(func.count(Campaign.id)).where(Campaign.status == CampaignStatus.ACTIVE)
        )
        completed_campaigns = await db.scalar(
            select(func.count(Campaign.id)).where(Campaign.status == CampaignStatus.COMPLETED)
        )
        draft_campaigns = await db.scalar(
            select(func.count(Campaign.id)).where(Campaign.status == CampaignStatus.DRAFT)
        )
        
        print(f"\n[캠페인 통계]")
        print(f"   전체 캠페인: {total_campaigns}개")
        print(f"   진행중: {active_campaigns}개")
        print(f"   완료: {completed_campaigns}개")
        print(f"   초안: {draft_campaigns}개")
        
        # 캠페인 목록
        campaigns = await db.execute(select(Campaign).order_by(Campaign.id))
        campaigns = campaigns.scalars().all()
        
        print(f"\n[캠페인 목록]")
        for campaign in campaigns:
            print(f"   {campaign.id}. {campaign.name} - {campaign.status} - 예산: {campaign.budget:,.0f}원")
            print(f"       클라이언트: {campaign.client_company}")
            print(f"       기간: {campaign.start_date.strftime('%Y-%m-%d')} ~ {campaign.end_date.strftime('%Y-%m-%d')}")
        
        # 구매요청 통계
        total_requests = await db.scalar(select(func.count(PurchaseRequest.id)))
        pending_requests = await db.scalar(
            select(func.count(PurchaseRequest.id)).where(PurchaseRequest.status == RequestStatus.PENDING)
        )
        approved_requests = await db.scalar(
            select(func.count(PurchaseRequest.id)).where(PurchaseRequest.status == RequestStatus.APPROVED)
        )
        completed_requests = await db.scalar(
            select(func.count(PurchaseRequest.id)).where(PurchaseRequest.status == RequestStatus.COMPLETED)
        )
        rejected_requests = await db.scalar(
            select(func.count(PurchaseRequest.id)).where(PurchaseRequest.status == RequestStatus.REJECTED)
        )
        
        print(f"\n[구매요청 통계]")
        print(f"   전체 구매요청: {total_requests}개")
        print(f"   대기: {pending_requests}개")
        print(f"   승인: {approved_requests}개")
        print(f"   완료: {completed_requests}개")
        print(f"   거절: {rejected_requests}개")
        
        # 구매요청 목록
        requests = await db.execute(
            select(PurchaseRequest)
            .join(User, PurchaseRequest.requester_id == User.id)
            .order_by(PurchaseRequest.id)
        )
        requests = requests.scalars().all()
        
        print(f"\n[구매요청 목록]")
        for request in requests:
            requester_result = await db.execute(
                select(User).where(User.id == request.requester_id)
            )
            requester = requester_result.scalar_one()
            
            print(f"   {request.id}. {request.title} - {request.status}")
            print(f"       요청자: {requester.name}")
            print(f"       금액: {request.amount:,.0f}원 x {request.quantity}개")
            print(f"       공급업체: {request.vendor}")
        
        # 예산 통계
        total_budget = await db.scalar(select(func.sum(Campaign.budget))) or 0
        active_budget = await db.scalar(
            select(func.sum(Campaign.budget)).where(Campaign.status == CampaignStatus.ACTIVE)
        ) or 0
        total_request_amount = await db.scalar(select(func.sum(PurchaseRequest.amount))) or 0
        approved_amount = await db.scalar(
            select(func.sum(PurchaseRequest.amount)).where(
                PurchaseRequest.status.in_([RequestStatus.APPROVED, RequestStatus.COMPLETED])
            )
        ) or 0
        
        print(f"\n[예산 통계]")
        print(f"   전체 캠페인 예산: {total_budget:,.0f}원")
        print(f"   진행중 캠페인 예산: {active_budget:,.0f}원")
        print(f"   전체 구매요청 금액: {total_request_amount:,.0f}원")
        print(f"   승인/완료된 구매요청 금액: {approved_amount:,.0f}원")
        
        print(f"\n" + "="*50)
        print("테스트 데이터 확인 완료!")


if __name__ == "__main__":
    asyncio.run(check_test_data())