#!/usr/bin/env python3
"""
Migration script to add manager_id column to campaigns table
Run this script to update existing database schema
"""

import asyncio
import os
import sys
sys.path.append(".")
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


async def run_migration():
    """Add manager_id column to campaigns table"""
    
    # Get database URL using app configuration
    database_url = settings.get_database_url
    if not database_url or "sqlite" in database_url:
        print("ERROR: PostgreSQL database not available. Currently using SQLite.")
        print("This migration requires a PostgreSQL database.")
        return False
    
    print(f"Using database: {database_url}")
    
    # Database URL is already properly formatted by settings
    
    # Create async engine
    engine = create_async_engine(database_url, echo=True)
    
    try:
        async with engine.begin() as conn:
            print("Adding manager_id column to campaigns table...")
            
            # Add manager_id column
            await conn.execute(text("""
                ALTER TABLE campaigns 
                ADD COLUMN IF NOT EXISTS manager_id INTEGER,
                ADD CONSTRAINT IF NOT EXISTS fk_campaigns_manager_id 
                FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE SET NULL;
            """))
            
            print("Migration completed successfully!")
            print("- Added manager_id column to campaigns table")
            print("- Added foreign key constraint to users table")
            
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        return False
    finally:
        await engine.dispose()
    
    return True


if __name__ == "__main__":
    print("Starting database migration...")
    success = asyncio.run(run_migration())
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
        exit(1)