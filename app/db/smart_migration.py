#!/usr/bin/env python3
"""
스마트 데이터 마이그레이션 시스템
기존 캠페인 데이터의 client_company 필드를 분석하여 자동으로 client_user_id를 연결
"""

import asyncio
import re
from typing import List, Tuple, Optional, Dict
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_engine, AsyncSessionLocal
from app.models.user import User
from app.models.campaign import Campaign


class SmartDataMigrator:
    """지능적 데이터 마이그레이션 클래스"""
    
    def __init__(self):
        self.user_cache = {}  # 성능 최적화를 위한 사용자 캐시
        
    async def load_user_cache(self, db: AsyncSession):
        """모든 사용자 정보를 캐시에 로드"""
        users = await db.execute(select(User))
        for user in users.scalars():
            # 이름 기반 매칭을 위한 정규화
            normalized_name = self.normalize_text(user.name)
            self.user_cache[user.id] = {
                'name': user.name,
                'normalized_name': normalized_name,
                'email': user.email,
                'company': user.company
            }
        print(f"✅ Loaded {len(self.user_cache)} users into cache")
    
    def normalize_text(self, text: str) -> str:
        """텍스트 정규화 (공백, 특수문자 제거)"""
        if not text:
            return ""
        # 공백, 괄호, 특수문자 제거하고 소문자로 변환
        return re.sub(r'[^\w가-힣]', '', text).lower()
    
    def extract_patterns(self, client_company: str) -> Dict[str, Optional[str]]:
        """client_company에서 다양한 패턴 추출"""
        if not client_company:
            return {}
        
        patterns = {}
        
        # 1. ID 패턴: "(ID: 123)" 또는 "(ID:123)"
        id_match = re.search(r'\(ID:\s*(\d+)\)', client_company)
        if id_match:
            patterns['user_id'] = int(id_match.group(1))
        
        # 2. 이름 패턴: 괄호 앞의 이름 추출
        name_match = re.search(r'^([^(]+)(?:\s*\(|$)', client_company)
        if name_match:
            patterns['name'] = name_match.group(1).strip()
        
        # 3. 이메일 패턴
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', client_company)
        if email_match:
            patterns['email'] = email_match.group(1)
        
        # 4. 회사명 패턴
        company_match = re.search(r'@([^)]+)', client_company)
        if company_match:
            patterns['company'] = company_match.group(1).strip()
            
        return patterns
    
    def find_matching_user_id(self, client_company: str) -> Optional[int]:
        """client_company 문자열에서 가장 적합한 user_id 찾기"""
        patterns = self.extract_patterns(client_company)
        
        # 1. 명시적 ID 패턴이 있으면 우선 사용
        if 'user_id' in patterns:
            user_id = patterns['user_id']
            if user_id in self.user_cache:
                return user_id
        
        # 2. 이름 기반 매칭
        if 'name' in patterns:
            search_name = self.normalize_text(patterns['name'])
            for user_id, user_info in self.user_cache.items():
                if user_info['normalized_name'] == search_name:
                    return user_id
        
        # 3. 이메일 기반 매칭
        if 'email' in patterns:
            for user_id, user_info in self.user_cache.items():
                if user_info['email'] and user_info['email'].lower() == patterns['email'].lower():
                    return user_id
        
        # 4. 회사명 기반 매칭 (부분 문자열)
        if 'company' in patterns:
            search_company = self.normalize_text(patterns['company'])
            for user_id, user_info in self.user_cache.items():
                if user_info['company']:
                    normalized_company = self.normalize_text(user_info['company'])
                    if search_company in normalized_company or normalized_company in search_company:
                        return user_id
        
        return None
    
    async def analyze_unmapped_campaigns(self, db: AsyncSession) -> List[Dict]:
        """매핑되지 않은 캠페인들 분석"""
        result = await db.execute(text("""
            SELECT id, name, client_company, creator_id
            FROM campaigns 
            WHERE client_user_id IS NULL 
            AND client_company IS NOT NULL 
            AND client_company != ''
            ORDER BY id
        """))
        
        unmapped_campaigns = []
        for row in result:
            patterns = self.extract_patterns(row.client_company)
            suggested_user_id = self.find_matching_user_id(row.client_company)
            
            unmapped_campaigns.append({
                'id': row.id,
                'name': row.name,
                'client_company': row.client_company,
                'creator_id': row.creator_id,
                'extracted_patterns': patterns,
                'suggested_user_id': suggested_user_id,
                'suggested_user_name': self.user_cache.get(suggested_user_id, {}).get('name') if suggested_user_id else None
            })
        
        return unmapped_campaigns
    
    async def execute_smart_migration(self, db: AsyncSession, dry_run: bool = False) -> Dict[str, int]:
        """지능적 마이그레이션 실행"""
        print(f"🔍 Starting smart migration (dry_run={dry_run})...")
        
        # 사용자 캐시 로드
        await self.load_user_cache(db)
        
        # 매핑되지 않은 캠페인 분석
        unmapped_campaigns = await self.analyze_unmapped_campaigns(db)
        
        stats = {
            'total_unmapped': len(unmapped_campaigns),
            'id_pattern_matches': 0,
            'name_matches': 0,
            'email_matches': 0,
            'company_matches': 0,
            'no_matches': 0,
            'updated': 0
        }
        
        print(f"📊 Found {stats['total_unmapped']} unmapped campaigns")
        
        for campaign in unmapped_campaigns:
            patterns = campaign['extracted_patterns']
            suggested_user_id = campaign['suggested_user_id']
            
            # 매칭 유형 분류
            if 'user_id' in patterns and suggested_user_id == patterns['user_id']:
                stats['id_pattern_matches'] += 1
                match_type = "ID_PATTERN"
            elif suggested_user_id:
                # 이름, 이메일, 회사명 중 어떤 것으로 매칭되었는지 확인
                user_info = self.user_cache.get(suggested_user_id, {})
                if 'name' in patterns and self.normalize_text(patterns['name']) == user_info.get('normalized_name', ''):
                    stats['name_matches'] += 1
                    match_type = "NAME_MATCH"
                elif 'email' in patterns and patterns['email'].lower() == user_info.get('email', '').lower():
                    stats['email_matches'] += 1
                    match_type = "EMAIL_MATCH"
                else:
                    stats['company_matches'] += 1
                    match_type = "COMPANY_MATCH"
            else:
                stats['no_matches'] += 1
                match_type = "NO_MATCH"
                continue
            
            print(f"  📌 Campaign #{campaign['id']}: '{campaign['name']}' -> User #{suggested_user_id} ({match_type})")
            print(f"     Original: {campaign['client_company']}")
            print(f"     Suggested: {campaign['suggested_user_name']}")
            
            # 실제 업데이트 (dry_run이 아닌 경우)
            if not dry_run and suggested_user_id:
                await db.execute(text("""
                    UPDATE campaigns 
                    SET client_user_id = :user_id 
                    WHERE id = :campaign_id
                """), {
                    'user_id': suggested_user_id,
                    'campaign_id': campaign['id']
                })
                stats['updated'] += 1
        
        if not dry_run:
            await db.commit()
            print(f"✅ Successfully updated {stats['updated']} campaigns")
        else:
            print(f"🔍 Dry run complete - would update {stats['total_unmapped'] - stats['no_matches']} campaigns")
        
        return stats


async def run_smart_migration(dry_run: bool = True):
    """스마트 마이그레이션 실행"""
    migrator = SmartDataMigrator()
    
    async with AsyncSessionLocal() as db:
        try:
            stats = await migrator.execute_smart_migration(db, dry_run=dry_run)
            
            print("\n📈 Migration Statistics:")
            print(f"  Total unmapped campaigns: {stats['total_unmapped']}")
            print(f"  ID pattern matches: {stats['id_pattern_matches']}")
            print(f"  Name matches: {stats['name_matches']}")
            print(f"  Email matches: {stats['email_matches']}")
            print(f"  Company matches: {stats['company_matches']}")
            print(f"  No matches found: {stats['no_matches']}")
            if not dry_run:
                print(f"  Successfully updated: {stats['updated']}")
            
            return stats
            
        except Exception as e:
            print(f"❌ Smart migration failed: {e}")
            raise


if __name__ == "__main__":
    # 먼저 dry run으로 실행하여 결과 확인
    print("=== DRY RUN ===")
    asyncio.run(run_smart_migration(dry_run=True))
    
    # 실제 실행하려면 아래 주석 해제
    # print("\n=== ACTUAL MIGRATION ===")
    # asyncio.run(run_smart_migration(dry_run=False))