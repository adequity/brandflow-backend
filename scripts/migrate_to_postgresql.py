"""
SQLite에서 PostgreSQL로 데이터 마이그레이션 스크립트
"""

import asyncio
import sqlite3
import asyncpg
import os
import sys
from datetime import datetime
from typing import Dict, Any, List

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


class DatabaseMigrator:
    """데이터베이스 마이그레이션 클래스"""
    
    def __init__(self):
        self.sqlite_path = "./brandflow.db"
        self.pg_config = {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "database": os.getenv("POSTGRES_DB", "brandflow"),
            "user": os.getenv("POSTGRES_USER", "brandflow_user"),
            "password": os.getenv("POSTGRES_PASSWORD", "your-secure-password")
        }
    
    def get_sqlite_data(self, table_name: str) -> List[Dict[str, Any]]:
        """SQLite에서 테이블 데이터 조회"""
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row  # dict-like access
        cursor = conn.cursor()
        
        try:
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError as e:
            print(f"Table {table_name} not found: {e}")
            return []
        finally:
            conn.close()
    
    async def create_postgresql_tables(self, pg_conn):
        """PostgreSQL에 테이블 생성"""
        
        # Users 테이블 생성
        await pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT '직원',
                company VARCHAR(200),
                contact VARCHAR(50),
                incentive_rate DECIMAL(5,2) DEFAULT 0.0,
                status VARCHAR(50) NOT NULL DEFAULT '활성',
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Campaigns 테이블 생성
        await pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id SERIAL PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                client_company VARCHAR(200),
                category VARCHAR(100),
                platform VARCHAR(100),
                start_date DATE,
                end_date DATE,
                budget DECIMAL(15,2),
                target_audience TEXT,
                requirements TEXT,
                status VARCHAR(50) NOT NULL DEFAULT '진행중',
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Purchase_requests 테이블 생성
        await pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS purchase_requests (
                id SERIAL PRIMARY KEY,
                requester_id INTEGER REFERENCES users(id),
                campaign_id INTEGER REFERENCES campaigns(id),
                item_name VARCHAR(200) NOT NULL,
                category VARCHAR(100),
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price DECIMAL(10,2) NOT NULL,
                total_amount DECIMAL(15,2) NOT NULL,
                vendor VARCHAR(200),
                request_reason TEXT,
                urgency VARCHAR(50) DEFAULT '보통',
                status VARCHAR(50) NOT NULL DEFAULT '대기중',
                approved_by INTEGER REFERENCES users(id),
                approved_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        print("✅ PostgreSQL 테이블 생성 완료")
    
    async def migrate_table_data(self, pg_conn, table_name: str, data: List[Dict[str, Any]]):
        """테이블 데이터를 PostgreSQL로 마이그레이션"""
        if not data:
            print(f"⚠️  {table_name} 테이블에 마이그레이션할 데이터가 없습니다.")
            return
        
        # 데이터 타입 변환 및 정리
        cleaned_data = []
        for row in data:
            cleaned_row = {}
            for key, value in row.items():
                if value is None:
                    cleaned_row[key] = None
                elif key in ['created_at', 'updated_at', 'approved_at'] and value:
                    # 날짜/시간 변환
                    try:
                        if isinstance(value, str):
                            cleaned_row[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        else:
                            cleaned_row[key] = value
                    except:
                        cleaned_row[key] = datetime.now()
                elif key in ['start_date', 'end_date'] and value:
                    # 날짜 변환
                    try:
                        cleaned_row[key] = datetime.fromisoformat(value).date()
                    except:
                        cleaned_row[key] = None
                else:
                    cleaned_row[key] = value
            cleaned_data.append(cleaned_row)
        
        # 테이블별 INSERT 쿼리 생성
        if table_name == "users":
            query = """
                INSERT INTO users (
                    id, name, email, hashed_password, role, company, contact, 
                    incentive_rate, status, is_active, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (email) DO UPDATE SET
                    name = EXCLUDED.name,
                    role = EXCLUDED.role,
                    company = EXCLUDED.company,
                    contact = EXCLUDED.contact,
                    incentive_rate = EXCLUDED.incentive_rate,
                    updated_at = EXCLUDED.updated_at
            """
            
            for row in cleaned_data:
                await pg_conn.execute(query, 
                    row['id'], row['name'], row['email'], row['hashed_password'],
                    row['role'], row.get('company'), row.get('contact'),
                    row.get('incentive_rate', 0.0), row['status'], row['is_active'],
                    row['created_at'], row['updated_at']
                )
        
        elif table_name == "campaigns":
            query = """
                INSERT INTO campaigns (
                    id, title, description, client_company, category, platform,
                    start_date, end_date, budget, target_audience, requirements,
                    status, created_by, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at
            """
            
            for row in cleaned_data:
                await pg_conn.execute(query,
                    row['id'], row['title'], row.get('description'),
                    row.get('client_company'), row.get('category'), row.get('platform'),
                    row.get('start_date'), row.get('end_date'), row.get('budget'),
                    row.get('target_audience'), row.get('requirements'),
                    row['status'], row.get('created_by'), row['created_at'], row['updated_at']
                )
        
        elif table_name == "purchase_requests":
            query = """
                INSERT INTO purchase_requests (
                    id, requester_id, campaign_id, item_name, category, quantity,
                    unit_price, total_amount, vendor, request_reason, urgency,
                    status, approved_by, approved_at, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    approved_by = EXCLUDED.approved_by,
                    approved_at = EXCLUDED.approved_at,
                    updated_at = EXCLUDED.updated_at
            """
            
            for row in cleaned_data:
                await pg_conn.execute(query,
                    row['id'], row['requester_id'], row.get('campaign_id'),
                    row['item_name'], row.get('category'), row['quantity'],
                    row['unit_price'], row['total_amount'], row.get('vendor'),
                    row.get('request_reason'), row.get('urgency', '보통'),
                    row['status'], row.get('approved_by'), row.get('approved_at'),
                    row['created_at'], row['updated_at']
                )
        
        print(f"✅ {table_name} 테이블 데이터 마이그레이션 완료: {len(cleaned_data)}건")
    
    async def update_sequences(self, pg_conn):
        """시퀀스 값을 현재 최대값으로 업데이트"""
        tables = ['users', 'campaigns', 'purchase_requests']
        
        for table in tables:
            max_id_result = await pg_conn.fetchrow(f"SELECT MAX(id) as max_id FROM {table}")
            max_id = max_id_result['max_id'] if max_id_result['max_id'] else 0
            
            if max_id > 0:
                await pg_conn.execute(f"SELECT setval('{table}_id_seq', {max_id})")
                print(f"✅ {table} 시퀀스 업데이트 완료: {max_id}")
    
    async def run_migration(self):
        """전체 마이그레이션 실행"""
        print("🚀 SQLite → PostgreSQL 마이그레이션 시작")
        
        # SQLite 파일 존재 확인
        if not os.path.exists(self.sqlite_path):
            print(f"❌ SQLite 파일을 찾을 수 없습니다: {self.sqlite_path}")
            return
        
        try:
            # PostgreSQL 연결
            pg_conn = await asyncpg.connect(**self.pg_config)
            print("✅ PostgreSQL 연결 성공")
            
            # 테이블 생성
            await self.create_postgresql_tables(pg_conn)
            
            # 데이터 마이그레이션
            tables_to_migrate = ['users', 'campaigns', 'purchase_requests']
            
            for table_name in tables_to_migrate:
                print(f"\n📊 {table_name} 테이블 마이그레이션 중...")
                sqlite_data = self.get_sqlite_data(table_name)
                await self.migrate_table_data(pg_conn, table_name, sqlite_data)
            
            # 시퀀스 업데이트
            await self.update_sequences(pg_conn)
            
            await pg_conn.close()
            print("\n🎉 마이그레이션 완료!")
            
        except Exception as e:
            print(f"❌ 마이그레이션 오류: {e}")
            raise


async def main():
    """메인 실행 함수"""
    migrator = DatabaseMigrator()
    await migrator.run_migration()


if __name__ == "__main__":
    asyncio.run(main())