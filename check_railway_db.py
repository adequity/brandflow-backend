#!/usr/bin/env python3
"""
Railway DB direct check and migration execution
"""
import asyncio
import asyncpg
import os
from datetime import datetime

# Railway database URL
DATABASE_URL = "postgresql://postgres:kAPUkGlWqoHwxIvtWaeukQuwcrZpSzuu@junction.proxy.rlwy.net:21652/railway"

async def check_and_migrate():
    """DB check and migration execution"""
    try:
        print("Connecting to Railway database...")
        conn = await asyncpg.connect(DATABASE_URL)
        
        # 1. Check campaigns table existence
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'campaigns'
        """)
        
        if not tables:
            print("ERROR: campaigns table does not exist!")
            return
        
        print("SUCCESS: campaigns table exists")
        
        # 2. Check current campaigns table structure
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'campaigns' 
            ORDER BY ordinal_position
        """)
        
        print("\nCurrent campaigns table structure:")
        existing_columns = set()
        for col in columns:
            existing_columns.add(col['column_name'])
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"  - {col['column_name']}: {col['data_type']} ({nullable})")
        
        # 3. Check start_date, end_date columns
        has_start_date = 'start_date' in existing_columns
        has_end_date = 'end_date' in existing_columns
        
        print(f"\nDate column status:")
        print(f"  - start_date: {'EXISTS' if has_start_date else 'MISSING'}")
        print(f"  - end_date: {'EXISTS' if has_end_date else 'MISSING'}")
        
        # 4. Add columns if missing
        if not has_start_date:
            print("\nAdding start_date column...")
            await conn.execute("""
                ALTER TABLE campaigns 
                ADD COLUMN start_date TIMESTAMP
            """)
            print("SUCCESS: start_date column added")
        
        if not has_end_date:
            print("\nAdding end_date column...")
            await conn.execute("""
                ALTER TABLE campaigns 
                ADD COLUMN end_date TIMESTAMP
            """)
            print("SUCCESS: end_date column added")
        
        # 5. Set default values for existing data
        if not has_start_date or not has_end_date:
            print("\nSetting default values for existing campaigns...")
            
            # Check current campaign count
            campaign_count = await conn.fetchval("SELECT COUNT(*) FROM campaigns")
            print(f"  - Total campaigns: {campaign_count}")
            
            if campaign_count > 0:
                # Set default values only for NULL items
                current_time = datetime.now()
                result = await conn.execute("""
                    UPDATE campaigns 
                    SET start_date = COALESCE(start_date, $1),
                        end_date = COALESCE(end_date, $1 + INTERVAL '30 days')
                    WHERE start_date IS NULL OR end_date IS NULL
                """, current_time)
                
                print(f"  - Updated campaigns: {result.split()[-1]}")
            
            # 6. Apply NOT NULL constraints
            print("\nApplying NOT NULL constraints...")
            await conn.execute("ALTER TABLE campaigns ALTER COLUMN start_date SET NOT NULL")
            await conn.execute("ALTER TABLE campaigns ALTER COLUMN end_date SET NOT NULL")
            print("SUCCESS: NOT NULL constraints applied")
        
        # 7. Check final table structure
        print("\nFinal campaigns table structure:")
        final_columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'campaigns' 
            ORDER BY ordinal_position
        """)
        
        for col in final_columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"  - {col['column_name']}: {col['data_type']} ({nullable})")
        
        # 8. Check sample data
        sample_data = await conn.fetch("""
            SELECT id, name, start_date, end_date 
            FROM campaigns 
            LIMIT 3
        """)
        
        if sample_data:
            print(f"\nSample campaign data:")
            for row in sample_data:
                print(f"  - ID {row['id']}: {row['name']}")
                print(f"    Start date: {row['start_date']}")
                print(f"    End date: {row['end_date']}")
        
        await conn.close()
        print(f"\nSUCCESS: Railway DB migration completed!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_and_migrate())