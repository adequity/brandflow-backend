#!/usr/bin/env python3
"""
Test script to directly execute update_null_campaign_dates() on Railway database
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from datetime import datetime, timedelta

# Railway PostgreSQL connection
DATABASE_URL = "postgresql+asyncpg://postgres:kAPUkGlWqoHwxIvtWaeukQuwcrZpSzuu@junction.proxy.rlwy.net:21652/railway"

async def test_update_null_campaign_dates():
    """Test update_null_campaign_dates function directly"""
    try:
        print("Connecting to Railway database...")
        async_engine = create_async_engine(
            DATABASE_URL,
            echo=True,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        
        async with async_engine.begin() as conn:
            print("Connected successfully!")
            
            # Check existing campaigns with NULL dates
            print("\n=== BEFORE UPDATE ===")
            result = await conn.execute(text("""
                SELECT id, name, budget, start_date, end_date
                FROM campaigns 
                WHERE start_date IS NULL OR end_date IS NULL
                LIMIT 5
            """))
            campaigns = result.fetchall()
            
            print(f"Found {len(campaigns)} campaigns with NULL dates:")
            for campaign in campaigns:
                print(f"  ID: {campaign.id}, Name: {campaign.name}, Budget: {campaign.budget}")
                print(f"  Start: {campaign.start_date}, End: {campaign.end_date}")
            
            if len(campaigns) > 0:
                print("\n=== EXECUTING UPDATE ===")
                # Execute the update
                current_time = datetime.now()
                end_time = current_time + timedelta(days=30)
                
                result = await conn.execute(text("""
                    UPDATE campaigns 
                    SET start_date = COALESCE(start_date, :start_date),
                        end_date = COALESCE(end_date, :end_date)
                    WHERE start_date IS NULL OR end_date IS NULL
                """), {
                    'start_date': current_time,
                    'end_date': end_time
                })
                
                updated_count = result.rowcount
                print(f"Updated {updated_count} campaigns")
                print(f"Default start_date: {current_time}")
                print(f"Default end_date: {end_time}")
                
                # Verify the update
                print("\n=== AFTER UPDATE ===")
                verify_result = await conn.execute(text("""
                    SELECT id, name, budget, start_date, end_date
                    FROM campaigns 
                    ORDER BY id
                    LIMIT 5
                """))
                updated_campaigns = verify_result.fetchall()
                
                print(f"Sample campaigns after update:")
                for campaign in updated_campaigns:
                    print(f"  ID: {campaign.id}, Name: {campaign.name}, Budget: {campaign.budget}")
                    print(f"  Start: {campaign.start_date}, End: {campaign.end_date}")
            else:
                print("All campaigns already have valid dates!")
                
        await async_engine.dispose()
        print("\n✅ Update completed successfully!")
        
    except Exception as e:
        print(f"❌ Failed to update campaign dates: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_update_null_campaign_dates())