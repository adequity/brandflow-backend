#!/usr/bin/env python3
"""
Simple script to fix client_user data using direct SQL
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def fix_client_data():
    """Fix client_user data using direct SQL"""

    database_url = os.getenv('DATABASE_URL')
    print(f"[INFO] Connecting to database...")

    # Fix URL format for asyncpg (remove +asyncpg)
    if database_url and '+asyncpg' in database_url:
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

    # Connect directly to PostgreSQL
    conn = await asyncpg.connect(database_url)

    try:
        print("[INFO] Checking campaign 47...")

        # Check current state of campaign 47
        campaign_data = await conn.fetchrow(
            "SELECT id, name, client_company, client_user_id FROM campaigns WHERE id = 47"
        )

        if not campaign_data:
            print("[ERROR] Campaign 47 not found")
            return

        print(f"[INFO] Campaign 47: {campaign_data['name']}")
        print(f"   Client company: {campaign_data['client_company']}")
        print(f"   Client user ID: {campaign_data['client_user_id']}")

        # Find a client user (preferably ID 2 as mentioned in debugging output)
        client_user = await conn.fetchrow(
            "SELECT id, name, email, role, client_company_name FROM users WHERE id = 2"
        )

        if not client_user:
            print("[ERROR] User ID 2 not found, looking for CLIENT users...")
            client_user = await conn.fetchrow(
                "SELECT id, name, email, role, client_company_name FROM users WHERE role = 'CLIENT' LIMIT 1"
            )

        if not client_user:
            print("[ERROR] No client user found!")
            return

        print(f"[FOUND] Client user: {client_user['name']} (ID: {client_user['id']}, Email: {client_user['email']})")

        # Update client user with company information if missing
        if not client_user['client_company_name']:
            print("[UPDATING] Adding company information to client user...")
            await conn.execute("""
                UPDATE users
                SET client_company_name = '테스트클라이언트회사',
                    client_business_number = '123-45-67890',
                    client_ceo_name = '홍길동',
                    client_company_address = '서울시 강남구 테스트로 123',
                    client_business_type = '서비스업',
                    client_business_item = '마케팅대행'
                WHERE id = $1
            """, client_user['id'])
            print("[SUCCESS] Client user company info updated")

        # Link campaign to client user
        if campaign_data['client_user_id'] != client_user['id']:
            print(f"[LINKING] Campaign 47 to client user {client_user['id']}")
            await conn.execute(
                "UPDATE campaigns SET client_user_id = $1 WHERE id = 47",
                client_user['id']
            )
            print("[SUCCESS] Campaign linked to client user")

        # Verify the fix
        print("\n[VERIFYING] Checking results...")
        result = await conn.fetchrow("""
            SELECT c.id, c.name, c.client_user_id,
                   u.name as client_name, u.client_company_name, u.client_business_number,
                   u.client_ceo_name, u.client_company_address, u.client_business_type, u.client_business_item
            FROM campaigns c
            LEFT JOIN users u ON c.client_user_id = u.id
            WHERE c.id = 47
        """)

        if result and result['client_user_id']:
            print("[SUCCESS] Verification successful:")
            print(f"   Client user ID: {result['client_user_id']}")
            print(f"   Client name: {result['client_name']}")
            print(f"   Company name: {result['client_company_name']}")
            print(f"   Business number: {result['client_business_number']}")
            print(f"   CEO name: {result['client_ceo_name']}")
            print(f"   Address: {result['client_company_address']}")
            print(f"   Business type: {result['client_business_type']}")
            print(f"   Business item: {result['client_business_item']}")
        else:
            print("[ERROR] Verification failed")

        print("\n[INFO] Fix completed successfully!")

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_client_data())