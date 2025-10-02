#!/usr/bin/env python3
"""
Railway에서 SQLAlchemy를 통해 products.company 컬럼을 수동으로 추가하는 스크립트
"""
import asyncio
from sqlalchemy import text
from app.db.database import get_async_db


async def manual_add_company_column():
    """SQLAlchemy를 통해 products.company 컬럼 추가"""

    print("Manual migration starting...")

    try:
        # 데이터베이스 연결
        async for db in get_async_db():
            try:
                print("Connected to Railway database")

                # 1. products.company 컬럼 존재 여부 확인
                print("Checking if products.company column exists...")
                result = await db.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'products' AND column_name = 'company'
                """))
                column_exists = result.fetchone()

                if column_exists:
                    print("SUCCESS: products.company column already exists")
                    return True

                print("Adding products.company column...")

                # 2. products 테이블에 company 컬럼 추가
                await db.execute(text("""
                    ALTER TABLE products
                    ADD COLUMN company VARCHAR(200) DEFAULT 'default_company'
                """))
                print("SUCCESS: products.company column added")

                # 3. company 컬럼에 인덱스 생성
                await db.execute(text("""
                    CREATE INDEX ix_products_company ON products (company)
                """))
                print("SUCCESS: products.company index created")

                # 4. 기존 데이터에 기본값 설정
                result = await db.execute(text("""
                    UPDATE products
                    SET company = 'default_company'
                    WHERE company IS NULL
                """))
                print("SUCCESS: Updated existing products with default company value")

                # 5. 변경사항 커밋
                await db.commit()
                print("SUCCESS: Changes committed to database")

                # 6. 결과 확인
                product_count = await db.execute(text("SELECT COUNT(*) FROM products"))
                count_result = product_count.fetchone()
                total_products = count_result[0] if count_result else 0

                company_count = await db.execute(text("SELECT COUNT(*) FROM products WHERE company IS NOT NULL"))
                company_result = company_count.fetchone()
                products_with_company = company_result[0] if company_result else 0

                print(f"Total products: {total_products}")
                print(f"Products with company set: {products_with_company}")

                print("SUCCESS: Railway database migration completed!")
                print("SUCCESS: STAFF campaign details page HTTP 500 error should be resolved!")

                return True

            except Exception as e:
                print(f"ERROR during migration: {str(e)}")
                await db.rollback()
                return False
            finally:
                await db.close()
                break

    except Exception as e:
        print(f"ERROR connecting to database: {str(e)}")
        return False


if __name__ == "__main__":
    result = asyncio.run(manual_add_company_column())
    if result:
        print("\n" + "="*50)
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print("Please test the STAFF campaign details page now.")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("MIGRATION FAILED!")
        print("="*50)
