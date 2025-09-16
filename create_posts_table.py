#!/usr/bin/env python3
"""
Posts 테이블 생성 스크립트
Railway PostgreSQL 데이터베이스에 posts 테이블을 생성합니다.
"""

import os
import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.base import Base
from app.models.post import Post
from app.models.campaign import Campaign
from app.models.product import Product

async def create_posts_table():
    """posts 테이블 생성"""
    try:
        # Railway Database URL
        database_url = settings.get_database_url
        print(f"데이터베이스 URL: {database_url[:50]}...")

        # 비동기 엔진 생성
        engine = create_async_engine(database_url, echo=True)

        # 테이블 생성
        async with engine.begin() as conn:
            print("Post 테이블 생성 중...")

            # posts 테이블 생성 SQL
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS posts (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    work_type VARCHAR(100) NOT NULL DEFAULT '블로그',
                    topic_status VARCHAR(50) NOT NULL DEFAULT '대기',
                    outline TEXT,
                    outline_status VARCHAR(50),
                    images JSON,
                    published_url TEXT,
                    order_request_status VARCHAR(50),
                    order_request_id INTEGER,
                    start_date VARCHAR(20),
                    due_date VARCHAR(20),
                    product_id INTEGER REFERENCES products(id),
                    quantity INTEGER DEFAULT 1,
                    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))

            print("✅ posts 테이블 생성 완료!")

        await engine.dispose()

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        raise

if __name__ == "__main__":
    print("Posts 테이블 생성을 시작합니다...")
    asyncio.run(create_posts_table())
    print("완료!")