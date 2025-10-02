#!/usr/bin/env python3
"""
Railway 데이터베이스에 products.company 컬럼을 수동으로 추가하는 스크립트
"""
import asyncio
import os
import asyncpg


async def add_products_company_column():
    """Railway PostgreSQL 데이터베이스에 products.company 컬럼 추가"""

    # Railway DATABASE_URL 환경변수 사용
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not found.")
        return False

    # asyncpg는 postgresql:// 형식만 지원하므로 +asyncpg 제거
    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        print("INFO: Converted DATABASE_URL from postgresql+asyncpg to postgresql format")

    try:
        print("Connecting to Railway PostgreSQL database...")
        conn = await asyncpg.connect(database_url)

        # 1. products.company 컬럼 존재 여부 확인
        print("Checking if products.company column exists...")
        column_check = await conn.fetchrow("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'products' AND column_name = 'company'
        """)

        if column_check:
            print("SUCCESS: products.company column already exists.")
            await conn.close()
            return True

        print("Adding products.company column...")

        # 2. products 테이블에 company 컬럼 추가
        await conn.execute("""
            ALTER TABLE products
            ADD COLUMN company VARCHAR(200) DEFAULT 'default_company'
        """)
        print("SUCCESS: products.company column added")

        # 3. company 컬럼에 인덱스 생성
        await conn.execute("""
            CREATE INDEX ix_products_company ON products (company)
        """)
        print("SUCCESS: products.company index created")

        # 4. 기존 데이터에 기본값 설정
        updated_rows = await conn.execute("""
            UPDATE products
            SET company = 'default_company'
            WHERE company IS NULL
        """)
        print(f"SUCCESS: Updated {updated_rows.split()[1]} existing products with default company value")

        # 5. 결과 확인
        product_count = await conn.fetchval("SELECT COUNT(*) FROM products")
        company_count = await conn.fetchval("SELECT COUNT(*) FROM products WHERE company IS NOT NULL")

        print(f"Total products: {product_count}")
        print(f"Products with company set: {company_count}")

        await conn.close()
        print("SUCCESS: Railway database migration completed!")
        return True

    except Exception as e:
        print(f"ERROR: {str(e)}")
        if 'conn' in locals():
            await conn.close()
        return False


async def verify_fix():
    """마이그레이션 성공 여부 검증"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        return False

    # asyncpg는 postgresql:// 형식만 지원하므로 +asyncpg 제거
    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

    try:
        conn = await asyncpg.connect(database_url)

        # products.company 컬럼으로 쿼리 테스트
        result = await conn.fetchrow("""
            SELECT id, name, company
            FROM products
            WHERE is_active = true
            LIMIT 1
        """)

        if result:
            print(f"SUCCESS: Test query succeeded: product '{result['name']}' (company: {result['company']})")
            await conn.close()
            return True
        else:
            print("WARNING: No active products found.")
            await conn.close()
            return True

    except Exception as e:
        print(f"ERROR: Verification failed: {str(e)}")
        return False


async def main():
    """메인 실행 함수"""
    print("Railway database migration starting...")
    print("=" * 50)

    # 1. products.company 컬럼 추가
    success = await add_products_company_column()

    if not success:
        print("ERROR: Migration failed")
        return

    print("\n" + "=" * 50)
    print("Verifying migration results...")

    # 2. 마이그레이션 결과 검증
    if await verify_fix():
        print("SUCCESS: Railway database migration completed!")
        print("SUCCESS: STAFF campaign details page HTTP 500 error should be resolved.")
    else:
        print("ERROR: Migration verification failed")


if __name__ == "__main__":
    asyncio.run(main())