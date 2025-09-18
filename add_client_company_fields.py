from app.db.database import async_engine as engine
from sqlalchemy import text
import asyncio

async def add_client_company_fields():
    """클라이언트 실제 회사 정보 컬럼들을 users 테이블에 추가"""

    columns_to_add = [
        ('client_company_name', 'VARCHAR(200)', '실제 회사명'),
        ('client_business_number', 'VARCHAR(20)', '실제 사업자번호'),
        ('client_ceo_name', 'VARCHAR(100)', '실제 대표자명'),
        ('client_company_address', 'VARCHAR(500)', '실제 회사 주소'),
        ('client_business_type', 'VARCHAR(100)', '실제 업태'),
        ('client_business_item', 'VARCHAR(100)', '실제 종목')
    ]

    async with engine.begin() as conn:
        for column_name, column_type, description in columns_to_add:
            # 컬럼이 존재하는지 확인
            result = await conn.execute(text(
                f"SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='{column_name}'"
            ))
            exists = result.fetchone()

            if not exists:
                print(f'Adding {column_name} column to users table... ({description})')
                await conn.execute(text(
                    f'ALTER TABLE users ADD COLUMN {column_name} {column_type}'
                ))
                print(f'✅ {column_name} column added successfully')
            else:
                print(f'✅ {column_name} column already exists')

if __name__ == "__main__":
    asyncio.run(add_client_company_fields())