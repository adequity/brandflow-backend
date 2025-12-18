"""
Game Asset Table Creation Script
Run directly to create game_assets table.
"""
import asyncio
import os
import sys
from sqlalchemy import text
from app.db.database import async_engine

# Fix Windows encoding issue
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


async def create_game_assets_table():
    """Create game_assets table"""

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS game_assets (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        category VARCHAR(50) DEFAULT 'etc',
        game_type VARCHAR(50) NOT NULL,
        image_url VARCHAR(500),
        usage_count INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """

    async with async_engine.begin() as conn:
        # Check if table exists
        check_table = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'game_assets'
            );
        """))
        table_exists = check_table.scalar()

        if table_exists:
            print("[OK] game_assets table already exists.")
        else:
            await conn.execute(text(create_table_sql))
            print("[OK] game_assets table created.")

        # Create index
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_game_assets_game_type ON game_assets(game_type);
        """))
        print("[OK] game_type index created.")

        # Add sample data (for testing)
        count_result = await conn.execute(text("SELECT COUNT(*) FROM game_assets"))
        count = count_result.scalar()

        if count == 0:
            # Sample assets
            sample_assets = [
                ("Hamburger", "Food", "same_picture", "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=200"),
                ("Pizza", "Food", "same_picture", "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=200"),
                ("Ice Cream", "Dessert", "same_picture", "https://images.unsplash.com/photo-1497034825429-c343d7c6a68f?w=200"),
                ("Coffee", "Drink", "same_picture", "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=200"),
                ("Cake", "Dessert", "same_picture", "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=200"),
                ("Salad", "Food", "same_picture", "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=200"),
                ("Smoothie", "Drink", "same_picture", "https://images.unsplash.com/photo-1546173159-315724a31696?w=200"),
                ("Pasta", "Food", "same_picture", "https://images.unsplash.com/photo-1481931098730-318b6f776db0?w=200"),
            ]

            for name, category, game_type, image_url in sample_assets:
                await conn.execute(text("""
                    INSERT INTO game_assets (name, category, game_type, image_url)
                    VALUES (:name, :category, :game_type, :image_url)
                """), {"name": name, "category": category, "game_type": game_type, "image_url": image_url})

            print(f"[OK] {len(sample_assets)} sample assets added.")
        else:
            print(f"[INFO] {count} assets already exist.")


if __name__ == "__main__":
    asyncio.run(create_game_assets_table())
    print("\n[DONE] Game asset table setup complete!")
