#!/usr/bin/env python3
"""
Production database data verification script
프로덕션 환경에서 실제 클라이언트 데이터 확인
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_production_data():
    """Production 환경의 실제 데이터 확인"""

    database_url = os.getenv('DATABASE_URL')
    print(f"[INFO] Connecting to production database...")

    # Fix URL format for asyncpg
    if database_url and '+asyncpg' in database_url:
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

    # Connect to PostgreSQL
    conn = await asyncpg.connect(database_url)

    try:
        print("\n=== PRODUCTION DATA VERIFICATION ===")

        # 1. Check campaign 47 with full JOIN
        print("\n[1] Campaign 47 with Client User Info:")
        campaign_with_client = await conn.fetchrow("""
            SELECT c.id, c.name, c.client_company, c.client_user_id,
                   u.id as user_id, u.name as user_name, u.email as user_email, u.role,
                   u.client_company_name, u.client_business_number, u.client_ceo_name,
                   u.client_company_address, u.client_business_type, u.client_business_item
            FROM campaigns c
            LEFT JOIN users u ON c.client_user_id = u.id
            WHERE c.id = 47
        """)

        if campaign_with_client:
            print(f"   Campaign ID: {campaign_with_client['id']}")
            print(f"   Campaign Name: {campaign_with_client['name']}")
            print(f"   Client Company: {campaign_with_client['client_company']}")
            print(f"   Client User ID: {campaign_with_client['client_user_id']}")
            print(f"   User Name: {campaign_with_client['user_name']}")
            print(f"   User Email: {campaign_with_client['user_email']}")
            print(f"   User Role: {campaign_with_client['role']}")
            print(f"   Client Company Name: {campaign_with_client['client_company_name']}")
            print(f"   Client Business Number: {campaign_with_client['client_business_number']}")
            print(f"   Client CEO Name: {campaign_with_client['client_ceo_name']}")
            print(f"   Client Address: {campaign_with_client['client_company_address']}")
            print(f"   Business Type: {campaign_with_client['client_business_type']}")
            print(f"   Business Item: {campaign_with_client['client_business_item']}")
        else:
            print("   [ERROR] Campaign 47 not found!")

        # 2. Check all users with CLIENT role
        print("\n[2] All CLIENT users:")
        client_users = await conn.fetch("""
            SELECT id, name, email, role,
                   client_company_name, client_business_number, client_ceo_name,
                   client_company_address, client_business_type, client_business_item
            FROM users
            WHERE role = 'CLIENT'
        """)

        for user in client_users:
            print(f"   User {user['id']}: {user['name']} ({user['email']})")
            print(f"      Company: {user['client_company_name']}")
            print(f"      Business No: {user['client_business_number']}")
            print(f"      CEO: {user['client_ceo_name']}")
            print("")

        # 3. Check user ID 2 specifically
        print("[3] User ID 2 Details:")
        user_2 = await conn.fetchrow("""
            SELECT id, name, email, role, created_at, updated_at,
                   client_company_name, client_business_number, client_ceo_name,
                   client_company_address, client_business_type, client_business_item
            FROM users
            WHERE id = 2
        """)

        if user_2:
            print(f"   ID: {user_2['id']}")
            print(f"   Name: {user_2['name']}")
            print(f"   Email: {user_2['email']}")
            print(f"   Role: {user_2['role']}")
            print(f"   Created: {user_2['created_at']}")
            print(f"   Updated: {user_2['updated_at']}")
            print(f"   Company Name: {user_2['client_company_name']}")
            print(f"   Business Number: {user_2['client_business_number']}")
            print(f"   CEO Name: {user_2['client_ceo_name']}")
            print(f"   Address: {user_2['client_company_address']}")
            print(f"   Business Type: {user_2['client_business_type']}")
            print(f"   Business Item: {user_2['client_business_item']}")
        else:
            print("   [ERROR] User ID 2 not found!")

        print("\n=== END VERIFICATION ===")

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_production_data())