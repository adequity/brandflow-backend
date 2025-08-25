#!/usr/bin/env python3
"""
BrandFlow SQLite to PostgreSQL Migration Script

이 스크립트는 SQLite 데이터베이스의 데이터를 PostgreSQL로 마이그레이션합니다.

사용법:
1. PostgreSQL 서버가 실행 중인지 확인
2. .env.postgresql 파일이 올바르게 설정되었는지 확인
3. python migrate_to_postgresql.py 실행
"""

import asyncio
import os
import sys
from typing import Dict, List, Any
import sqlite3
import asyncpg
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
import json

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.models.base import Base
from app.models import *  # 모든 모델 임포트


class DatabaseMigrator:
    def __init__(self):
        self.sqlite_db = "brandflow.db"
        self.postgres_url = "postgresql://brandflow_user:brandflow_password_2024@localhost:5432/brandflow"
        
    async def check_postgresql_connection(self) -> bool:
        """PostgreSQL 연결 확인"""
        try:
            conn = await asyncpg.connect(self.postgres_url)
            await conn.close()
            print("✅ PostgreSQL 연결 성공")
            return True
        except Exception as e:
            print(f"❌ PostgreSQL 연결 실패: {e}")
            print(f"PostgreSQL 서버가 실행 중인지 확인하고 docker-compose up -d postgres를 실행하세요.")
            return False
    
    def check_sqlite_exists(self) -> bool:
        """SQLite 데이터베이스 존재 확인"""
        if not os.path.exists(self.sqlite_db):
            print(f"❌ SQLite 데이터베이스를 찾을 수 없습니다: {self.sqlite_db}")
            return False
        print(f"✅ SQLite 데이터베이스 발견: {self.sqlite_db}")
        return True
    
    async def create_postgresql_schema(self):
        """PostgreSQL에 스키마 생성"""
        print("🔧 PostgreSQL 스키마 생성 중...")
        
        engine = create_async_engine(self.postgres_url.replace("postgresql://", "postgresql+asyncpg://"))
        
        async with engine.begin() as conn:
            # 기존 테이블 삭제 (개발용)
            await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
            await conn.execute(text("CREATE SCHEMA public;"))
            
            # 모든 테이블 생성
            await conn.run_sync(Base.metadata.create_all)
        
        await engine.dispose()
        print("✅ PostgreSQL 스키마 생성 완료")
    
    def extract_sqlite_data(self) -> Dict[str, List[Dict]]:
        """SQLite에서 데이터 추출"""
        print("📊 SQLite 데이터 추출 중...")
        
        conn = sqlite3.connect(self.sqlite_db)
        conn.row_factory = sqlite3.Row  # dict-like access
        cursor = conn.cursor()
        
        data = {}
        
        # 테이블 목록 가져오기
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            data[table] = [dict(row) for row in rows]
            print(f"  - {table}: {len(rows)}개 레코드")
        
        conn.close()
        print(f"✅ SQLite 데이터 추출 완료 ({len(tables)}개 테이블)")
        return data
    
    async def insert_postgresql_data(self, data: Dict[str, List[Dict]]):
        """PostgreSQL에 데이터 삽입"""
        print("📝 PostgreSQL에 데이터 삽입 중...")
        
        conn = await asyncpg.connect(self.postgres_url)
        
        # 테이블 순서 (외래키 제약 조건 고려)
        table_order = [
            'users',
            'campaigns', 
            'purchase_requests',
            'products',
            'sales',
            'company_logos'
        ]
        
        for table in table_order:
            if table not in data or not data[table]:
                print(f"  - {table}: 데이터 없음")
                continue
                
            records = data[table]
            print(f"  - {table}: {len(records)}개 레코드 삽입 중...")
            
            if records:
                # 첫 번째 레코드의 키를 사용하여 컬럼 목록 생성
                columns = list(records[0].keys())
                placeholders = ', '.join([f'${i+1}' for i in range(len(columns))])
                
                query = f"""
                INSERT INTO {table} ({', '.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
                """
                
                # 각 레코드를 튜플로 변환
                values = []
                for record in records:
                    # JSON 필드가 있다면 문자열로 변환
                    row = []
                    for col in columns:
                        val = record[col]
                        if isinstance(val, (dict, list)):
                            val = json.dumps(val)
                        row.append(val)
                    values.append(tuple(row))
                
                try:
                    await conn.executemany(query, values)
                    print(f"    ✅ {table} 완료")
                except Exception as e:
                    print(f"    ❌ {table} 실패: {e}")
        
        await conn.close()
        print("✅ PostgreSQL 데이터 삽입 완료")
    
    async def verify_migration(self, original_data: Dict[str, List[Dict]]):
        """마이그레이션 결과 검증"""
        print("🔍 마이그레이션 결과 검증 중...")
        
        conn = await asyncpg.connect(self.postgres_url)
        
        for table, original_records in original_data.items():
            if not original_records:
                continue
                
            result = await conn.fetch(f"SELECT COUNT(*) as count FROM {table}")
            pg_count = result[0]['count']
            original_count = len(original_records)
            
            if pg_count == original_count:
                print(f"  ✅ {table}: {pg_count}/{original_count}")
            else:
                print(f"  ⚠️  {table}: {pg_count}/{original_count} (불일치)")
        
        await conn.close()
        print("✅ 검증 완료")
    
    async def run_migration(self):
        """전체 마이그레이션 실행"""
        print("🚀 BrandFlow PostgreSQL 마이그레이션 시작")
        print("="*50)
        
        # 1. 연결 확인
        if not await self.check_postgresql_connection():
            return False
            
        if not self.check_sqlite_exists():
            return False
        
        # 2. SQLite 데이터 추출
        original_data = self.extract_sqlite_data()
        
        # 3. PostgreSQL 스키마 생성
        await self.create_postgresql_schema()
        
        # 4. 데이터 마이그레이션
        await self.insert_postgresql_data(original_data)
        
        # 5. 검증
        await self.verify_migration(original_data)
        
        print("="*50)
        print("🎉 마이그레이션 완료!")
        print("\n다음 단계:")
        print("1. .env.postgresql 파일을 .env로 복사")
        print("2. FastAPI 서버 재시작")
        print("3. 애플리케이션 테스트")
        
        return True


async def main():
    migrator = DatabaseMigrator()
    success = await migrator.run_migration()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)