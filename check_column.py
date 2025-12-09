import asyncio
import os
from sqlalchemy import create_engine, inspect, text

# Railway PostgreSQL 연결
DATABASE_URL = "postgresql://postgres:Dlathfwns123@autorack.proxy.rlwy.net:25257/railway"

engine = create_engine(DATABASE_URL)

# posts 테이블 컬럼 확인
inspector = inspect(engine)
columns = inspector.get_columns('posts')

print("현재 posts 테이블의 컬럼:")
column_names = [col['name'] for col in columns]
for name in sorted(column_names):
    print(f"  - {name}")

# product_name 컬럼 확인
if 'product_name' in column_names:
    print("\n✅ product_name 컬럼이 이미 존재합니다.")
else:
    print("\n❌ product_name 컬럼이 없습니다!")
    print("   마이그레이션이 필요합니다.")

# 실제 데이터 확인
with engine.connect() as conn:
    result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'posts' AND column_name = 'product_name'"))
    exists = result.fetchone()
    
    if exists:
        print("\n데이터베이스에 product_name 컬럼 확인됨")
        
        # 샘플 데이터 확인
        result = conn.execute(text("SELECT id, title, product_name FROM posts WHERE product_name IS NOT NULL LIMIT 5"))
        rows = result.fetchall()
        if rows:
            print("\nproduct_name이 있는 데이터:")
            for row in rows:
                print(f"  ID {row[0]}: {row[1]} -> {row[2]}")
        else:
            print("\nproduct_name 값이 있는 데이터가 없습니다.")
    else:
        print("\n데이터베이스에 product_name 컬럼 없음!")
