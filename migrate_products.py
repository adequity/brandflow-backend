#!/usr/bin/env python3
"""
Add company field to products table for data segregation
Run this script once to migrate the database schema
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def migrate_products_table():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment")
        return False

    # Convert SQLAlchemy URL to asyncpg URL
    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

    try:
        print("Connecting to database...")
        conn = await asyncpg.connect(database_url)

        print("Adding company column to products table...")

        # Add the company column
        await conn.execute("""
            ALTER TABLE products ADD COLUMN IF NOT EXISTS company VARCHAR(200);
        """)
        print("Added company column")

        # Update existing products to use a default company name
        result = await conn.execute("""
            UPDATE products SET company = 'default_company' WHERE company IS NULL;
        """)
        print(f"Updated {result.split()[-1]} existing products with default company")

        # Make the column NOT NULL after setting default values
        await conn.execute("""
            ALTER TABLE products ALTER COLUMN company SET NOT NULL;
        """)
        print("Set company column as NOT NULL")

        # Add index for performance
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_company ON products(company);
        """)
        print("Created index on company column")

        print("Migration completed successfully!")

        # Show table info
        rows = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'products'
            ORDER BY ordinal_position;
        """)

        print("\nProducts table structure:")
        for row in rows:
            print(f"  {row['column_name']}: {row['data_type']} ({'NULL' if row['is_nullable'] == 'YES' else 'NOT NULL'})")

        await conn.close()
        return True

    except Exception as e:
        print(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(migrate_products_table())
    exit(0 if success else 1)