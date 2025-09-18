from app.database import engine
from sqlalchemy import text
import asyncio

async def check_and_add_business_number():
    # 컬럼이 존재하는지 확인
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='business_number'"
        ))
        exists = result.fetchone()

        if not exists:
            print('Adding business_number column to users table...')
            await conn.execute(text(
                'ALTER TABLE users ADD COLUMN business_number VARCHAR(20)'
            ))
            print('✅ business_number column added successfully')
        else:
            print('✅ business_number column already exists')

if __name__ == "__main__":
    asyncio.run(check_and_add_business_number())