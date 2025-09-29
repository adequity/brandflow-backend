#!/usr/bin/env python3
"""
Fix client_user data for proper document generation
"""
import asyncio
from app.db.database import get_async_db
from app.models.campaign import Campaign
from app.models.user import User, UserRole
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload

async def fix_client_data():
    """Fix client_user data for campaign ID 47 and others"""

    # Get database session
    db = await anext(get_async_db())

    try:
        print("[FIXING] Starting client data fix...")

        # Check campaign 47 specifically
        campaign_query = select(Campaign).options(
            joinedload(Campaign.creator),
            joinedload(Campaign.client_user)
        ).where(Campaign.id == 47)

        result = await db.execute(campaign_query)
        campaign = result.scalar_one_or_none()

        if not campaign:
            print("[ERROR] Campaign 47 not found")
            return

        print(f"[INFO] Campaign 47: {campaign.name}")
        print(f"   Client company: {campaign.client_company}")
        print(f"   Client user ID: {campaign.client_user_id}")

        if campaign.client_user:
            print(f"   Client user: {campaign.client_user.name} ({campaign.client_user.email})")
            print(f"   Client company name: {campaign.client_user.client_company_name}")
            print(f"   Client business number: {campaign.client_user.client_business_number}")
        else:
            print("   [ERROR] No client_user linked!")

        # Find a suitable client user to link (ID 2 from user's debug output)
        client_user_query = select(User).where(User.id == 2)
        result = await db.execute(client_user_query)
        client_user = result.scalar_one_or_none()

        if not client_user:
            print("[ERROR] User ID 2 not found, checking for CLIENT users...")
            # Find any client user
            client_query = select(User).where(User.role == UserRole.CLIENT).limit(1)
            result = await db.execute(client_query)
            client_user = result.scalar_one_or_none()

        if client_user:
            print(f"[FOUND] Client user: {client_user.name} ({client_user.email})")

            # Update client user with company information if missing
            if not client_user.client_company_name:
                print("[UPDATING] Client user with company information...")
                client_user.client_company_name = "테스트클라이언트회사"
                client_user.client_business_number = "123-45-67890"
                client_user.client_ceo_name = "홍길동"
                client_user.client_company_address = "서울시 강남구 테스트로 123"
                client_user.client_business_type = "서비스업"
                client_user.client_business_item = "마케팅대행"
                await db.commit()
                print("[SUCCESS] Client user company info updated")

            # Link campaign to client user
            if campaign.client_user_id != client_user.id:
                print(f"[LINKING] Campaign 47 to client user {client_user.id}")
                campaign.client_user_id = client_user.id
                await db.commit()
                print("[SUCCESS] Campaign linked to client user")
        else:
            print("[ERROR] No client user found to link")

        # Verify the fix
        print("\n[VERIFYING] Checking fix...")
        verify_query = select(Campaign).options(
            joinedload(Campaign.creator),
            joinedload(Campaign.client_user)
        ).where(Campaign.id == 47)

        result = await db.execute(verify_query)
        verified_campaign = result.scalar_one_or_none()

        if verified_campaign and verified_campaign.client_user:
            print("[SUCCESS] Verification successful:")
            print(f"   Client user: {verified_campaign.client_user.name}")
            print(f"   Company name: {verified_campaign.client_user.client_company_name}")
            print(f"   Business number: {verified_campaign.client_user.client_business_number}")
            print(f"   CEO name: {verified_campaign.client_user.client_ceo_name}")
            print(f"   Address: {verified_campaign.client_user.client_company_address}")
            print(f"   Business type: {verified_campaign.client_user.client_business_type}")
            print(f"   Business item: {verified_campaign.client_user.client_business_item}")
        else:
            print("[ERROR] Verification failed")

    except Exception as e:
        print(f"[ERROR] {e}")
        await db.rollback()
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(fix_client_data())