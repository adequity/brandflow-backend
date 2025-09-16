import asyncio
import sys
import os

# 현재 디렉터리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.database import get_async_db

async def create_order_requests_table():
    """order_requests 테이블 생성"""

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS order_requests (
        id SERIAL PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        description TEXT,
        status VARCHAR(50) NOT NULL DEFAULT '대기',
        cost_price INTEGER,
        resource_type VARCHAR(100),
        post_id INTEGER NOT NULL REFERENCES posts(id),
        user_id INTEGER NOT NULL REFERENCES users(id),
        campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
        is_active BOOLEAN DEFAULT TRUE
    );

    -- 인덱스 추가
    CREATE INDEX IF NOT EXISTS idx_order_requests_post_id ON order_requests(post_id);
    CREATE INDEX IF NOT EXISTS idx_order_requests_user_id ON order_requests(user_id);
    CREATE INDEX IF NOT EXISTS idx_order_requests_campaign_id ON order_requests(campaign_id);
    CREATE INDEX IF NOT EXISTS idx_order_requests_status ON order_requests(status);
    """

    db_gen = get_async_db()
    db = await anext(db_gen)

    try:
        print("Creating order_requests table...")

        # SQL 실행
        await db.execute(text(create_table_sql))
        await db.commit()

        print("✅ order_requests table created successfully!")

        # 테이블 정보 확인
        result = await db.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'order_requests'
            ORDER BY ordinal_position;
        """))

        columns = result.fetchall()
        print("\nTable structure:")
        for column in columns:
            print(f"  - {column.column_name}: {column.data_type} {'NULL' if column.is_nullable == 'YES' else 'NOT NULL'}")

    except Exception as e:
        print(f"❌ Error creating table: {e}")
        await db.rollback()
        raise

    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(create_order_requests_table())