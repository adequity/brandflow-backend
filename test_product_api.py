#!/usr/bin/env python3
"""
Test script to check if Product table has company column and test API
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def test_product_table_schema():
    database_url = os.getenv('DATABASE_URL')
    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

    try:
        print("Connecting to database...")
        conn = await asyncpg.connect(database_url)

        # Check if products table exists and show its structure
        print("\nChecking products table structure...")
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'products'
            ORDER BY ordinal_position;
        """)

        print("Products table columns:")
        for col in columns:
            print(f"  {col['column_name']}: {col['data_type']} ({'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'})")

        # Check if company column exists
        company_col = [col for col in columns if col['column_name'] == 'company']
        if company_col:
            print("\n✅ Company column exists!")

            # Check existing products
            products = await conn.fetch("SELECT id, name, company FROM products LIMIT 5;")
            print(f"\nExisting products ({len(products)}):")
            for product in products:
                print(f"  ID {product['id']}: {product['name']} (company: {product['company']})")
        else:
            print("\n❌ Company column missing - need to add it")

        await conn.close()
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_product_table_schema())
    exit(0 if success else 1)